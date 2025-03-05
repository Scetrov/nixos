let
  root = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJ4+AJpii7j0hNxwfVPnW+LVXBrp41GLZ4qjBZtC50mb";
  scetrov_hsm = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQDB7n7NyXkm6OucNqS9ExJPUJk/+jhcIxTJD3RnEt2IywDvHWUOBBEcfpOxprj54UsJDrfAslIvhFZkjEi+3Tgow1qC7+HVS3GfNu1YCP+MmTOnnEXgAhtaM7LTVFgt9QYEZeSpgrIIaKSlb515ln4Ghy+Jehbs06V6TcJYG/qIQd1RXN40O13VEyXmNAVRSf9ra7Emfg1OLzu7wabhxLqeLGBJ2cf0QKf0+ip+jYqbq/D2ZsCBYmGgQcKiopuCW7a51zzu/Df6G+SJS2yzWwZx1PjJ0yqUFWpuVDlRJi2sBbBTL1TUftMzRiZsyQPrS/eAlGLxzGjmvjzZ3pLZtD5xc6Qs7By/r/5Acxbp+2wn3fuo6lVmD5P54R0PsQyw7jrV7C7Zb7Cl7EuXZqW3Pm42aowq4skstTmdXsZZx0RkFvFaxDw5IFtC78E5Dwy/4pECLNXQ8stc6A5MKElGwHhcABK8IdUGf6R0lU4yEzknb7KhvERZRKEslQh3Jcn+7zScc5WBbjT3SMEdySWPMwreOpe1gnt+6MSf/8lpQCyBOP1Mr4/SSa95pJpWyRr1OSPi0KgOvSTVwppG6thcV1fRpGsDtpPB192KKrzInP3fxF0UOT3PhLgn7zZAlyGBAIel4m/zK0tqjL3kG2CNwnOkMrq5CTdK1JS7KnK4a/rxCw==";
  scetrov_bastion = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQDwzBwHyUdD/SVJygUmn+Dr8zwEttHMDxULn7f8CJQhnBaBZROAwuhIDCbgVKqwFqDbDI1domlGwMXUUSB1OGdCEXCE/YOtnYidvxhGIjR7uDgIwnMBL+eqzfH2OGKJf+qxsdLPg5ujhCUD0tAxP6Q0C9ur0o/cjE3228vU0VVOYpnKVpJevrDbi0ZIQf6cAxntKGkJgSFaMw5zdxeVWhOutK/dkr9SY6zjJs3aOPDo/FykWd5vDbfkHpQv0R3eB5fYiJJAxmlSL32YjdNc5aHRqcpJ/AxpX5fxMaKp9EnpnLBEQpl15A5iXlAxYLYeWb0EKJmLFwdvvsT4ux7MUKry5OLzyG/2ySqn12gM/mCze6hb6RWDcxDbHJmyvnopRAwVoKmVMhKf8tsDhWruH8d7MaOya1wwi93VDdG3KKJGwQX53GFnWch68k7aplglUt1sQKmjrCkXR8o2l/lftr/3xi0fF5nqakYYoyqA9IhlHe9PdJxnjOr54FCcgH21Mtc2CTY17mgWD45KyfvIyKOzyU8Hb4JlY3L1VXgjmLEBDpOB/jXxmV/8UUisupzyaveck0ypj4MX7IsPwny5XZc/PXuWFuVV2gYvDcBNAde/jyW16rrzYI2xGbDzc9OCa0gUES68G0Xs37py7Bk0SC13dWX6akI7bPnKunIn4ZHicQ==";
  users = [ root scetrov_hsm scetrov_bastion ];

  devenv = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAID/F3dBtSPoouR5qVTHCJTsVVgPBFTFJB1WVxnUkvgKa";
  woodford = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIF6a5bYzqwYWOJ2ORbg4ANoALIGUfO2fVwLW9UyWfq50";
  habiki = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJ6Gw0SitGQ9Z2WcxD/KyS142YlBZYg6aFeYymRIdMFR";
  systems = [ devenv woodford habiki ];
in
{
  "user_password_hashed.age".publicKeys = users ++ systems;
  "ssh_hsm_key.age".publicKeys = users ++ systems;
  "ssh_bastion_key.age".publicKeys = users ++ systems;
  "wireless_pskraw.age".publicKeys = users ++ systems;
  "wireless_ssid.age".publicKeys = users ++ systems;
  "cloudflare_dns_zone_api_key.age".publicKeys = users ++ systems;
  "cloudflare_email.age".publicKeys = users ++ systems;
}