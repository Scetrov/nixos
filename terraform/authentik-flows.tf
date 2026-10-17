# Brand selection is controlled separately; false is declarative rollback.
# Existing credentials, packaged fallback stages, and the helper's explicit
# default-authentication-flow remain unchanged.
data "authentik_stage" "fallback_password" {
  name = "default-authentication-password"
}

data "authentik_stage" "fallback_mfa" {
  name = "default-authentication-mfa-validation"
}

data "authentik_stage" "existing_session_login" {
  name = "default-authentication-login"
}

resource "authentik_flow" "passkey_candidate" {
  name           = "Passkey-first candidate"
  slug           = "passkey-first-candidate"
  title          = "Sign in"
  designation    = "authentication"
  authentication = "none"
}

# Native explicit validation opens the passkey prompt before identification.
resource "authentik_stage_authenticator_validate" "passkey_candidate" {
  name                       = "passkey-first-candidate-validation"
  device_classes             = ["webauthn"]
  not_configured_action      = "deny"
  webauthn_user_verification = "required"
  last_auth_threshold        = "seconds=0"
}

resource "authentik_policy_expression" "passkey_candidate_entry" {
  name              = "passkey-first-candidate-entry"
  execution_logging = false
  expression        = <<-PYTHON
    plan = request.context.get("flow_plan")
    if not plan:
        return True
    # Capture during execution, not cached planning. Keep the destination in
    # this native plan, not a separate session-wide handoff slot.
    params = request.http_request.session.get("authentik/flows/get", {})
    if "passkey_return_target" not in plan.context:
        target = params.get("next", "/if/user/")
        # Native redirect context is trusted by the executor. Admit only a
        # bounded root-relative path, never an external or ambiguous URL.
        valid = (
            isinstance(target, str)
            and 0 < len(target) <= 8192
            and target.startswith("/")
            and not target.startswith("//")
            and "\\" not in target
            and not any(ord(char) < 32 or ord(char) == 127 for char in target)
        )
        plan.context["passkey_return_target"] = target if valid else "/if/user/"
    plan.context["redirect"] = plan.context["passkey_return_target"]
    # Opting for password skips only the initial passkey attempt. It does not
    # authenticate a user or exempt them from password/applicable MFA.
    return params.get("use_password") != "1"
  PYTHON
}

resource "authentik_flow_stage_binding" "passkey_initial_validation" {
  target               = authentik_flow.passkey_candidate.uuid
  stage                = authentik_stage_authenticator_validate.passkey_candidate.id
  order                = 10
  evaluate_on_plan     = false
  re_evaluate_policies = true
}

resource "authentik_policy_binding" "passkey_initial_validation" {
  target         = authentik_flow_stage_binding.passkey_initial_validation.id
  policy         = authentik_policy_expression.passkey_candidate_entry.id
  order          = 0
  failure_result = true
}

# Fallback identification must not restart a conditional/modal passkey prompt.
resource "authentik_stage_identification" "passkey_candidate" {
  name                      = "passkey-first-candidate-identification"
  user_fields               = ["username", "email"]
  pretend_user_exists       = true
  show_matched_user         = true
  case_insensitive_matching = true
}

# Only trusted native success in this plan can bypass identification/password/
# MFA. Query markers, a chosen URL, or credential presence are not success.
resource "authentik_policy_expression" "passkey_candidate_needs_fallback" {
  name              = "passkey-first-candidate-needs-fallback"
  execution_logging = false
  expression        = <<-PYTHON
    plan = request.context.get("flow_plan")
    if not plan:
        return True
    return plan.context.get("auth_method") != "auth_webauthn_pwl"
  PYTHON
}

resource "authentik_flow_stage_binding" "passkey_identification" {
  target               = authentik_flow.passkey_candidate.uuid
  stage                = authentik_stage_identification.passkey_candidate.id
  order                = 20
  evaluate_on_plan     = false
  re_evaluate_policies = true
}

resource "authentik_policy_binding" "passkey_identification" {
  target         = authentik_flow_stage_binding.passkey_identification.id
  policy         = authentik_policy_expression.passkey_candidate_needs_fallback.id
  order          = 0
  failure_result = true
}

resource "authentik_flow_stage_binding" "passkey_fallback_password" {
  target               = authentik_flow.passkey_candidate.uuid
  stage                = data.authentik_stage.fallback_password.id
  order                = 30
  evaluate_on_plan     = false
  re_evaluate_policies = true
}

resource "authentik_policy_binding" "passkey_fallback_password" {
  target         = authentik_flow_stage_binding.passkey_fallback_password.id
  policy         = authentik_policy_expression.passkey_candidate_needs_fallback.id
  order          = 0
  failure_result = true
}

resource "authentik_flow_stage_binding" "passkey_fallback_mfa" {
  target               = authentik_flow.passkey_candidate.uuid
  stage                = data.authentik_stage.fallback_mfa.id
  order                = 40
  evaluate_on_plan     = false
  re_evaluate_policies = true
}

resource "authentik_policy_binding" "passkey_fallback_mfa" {
  target         = authentik_flow_stage_binding.passkey_fallback_mfa.id
  policy         = authentik_policy_expression.passkey_candidate_needs_fallback.id
  order          = 0
  failure_result = true
}

resource "authentik_flow_stage_binding" "passkey_session" {
  target = authentik_flow.passkey_candidate.uuid
  stage  = data.authentik_stage.existing_session_login.id
  order  = 100
}

# Preserve the previously shared direct URL as a native context-preserving alias.
resource "authentik_flow" "passkey_explicit_candidate" {
  name           = "Explicit passkey candidate"
  slug           = "passkey-explicit-candidate"
  title          = "Sign in with a passkey"
  designation    = "authentication"
  authentication = "none"
}

resource "authentik_stage_redirect" "passkey_candidate" {
  name         = "passkey-first-candidate-redirect"
  mode         = "flow"
  target_flow  = authentik_flow.passkey_candidate.uuid
  keep_context = true
}

resource "authentik_flow_stage_binding" "passkey_explicit_validation" {
  target = authentik_flow.passkey_explicit_candidate.uuid
  stage  = authentik_stage_redirect.passkey_candidate.id
  order  = 10
}
