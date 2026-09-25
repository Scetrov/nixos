#!/usr/bin/env python3
"""Check the declarative Project Zomboid operations dashboard contract."""

import json
import pathlib
import re
import sys


def main(root: pathlib.Path) -> None:
    dashboard = json.loads((root / "terraform/dashboards/project-zomboid-service.json").read_text())
    catalog = json.loads((root / "terraform/dashboards/service-catalog.json").read_text())
    terraform = (root / "terraform/grafana.tf").read_text()
    assert dashboard["uid"] == "svc-project-zomboid"
    assert dashboard["refresh"] == "30s"
    assert dashboard["time"] == {"from": "now-6h", "to": "now"}
    panels = {p["title"]: p for p in dashboard["panels"]}
    info = panels["More info"]
    assert info["collapsed"] and info["panels"][0]["title"] == "Signal Coverage"
    assert all(panels[title]["options"]["textMode"] == "value" for title in (
        "Native scrape", "Sample age", "Online Players", "Server FPS", "JVM Heap Used", "JVM uptime"
    ))
    assert "Online Player Location Coverage" not in panels and "Map Empty State" not in panels
    events = panels["Events / rolling hour"]
    assert len(events["targets"]) == 3 and all("increase(" in t["expr"] and "[1h]" in t["expr"] for t in events["targets"])
    assert dashboard["templating"]["list"][0]["hide"] == 1
    map_panel = panels["Player path"]
    assert map_panel["type"] == "geomap" and map_panel["gridPos"]["w"] == 12
    assert {"player_x", "player_y"} == {
        re.search(r"player_(?:x|y)", t["expr"]).group(0) for t in map_panel["targets"]
    }
    assert all("/ 111319.4908" in t["expr"] for t in map_panel["targets"])
    basemap = map_panel["options"]["basemap"]
    assert basemap["type"] == "xyz"
    assert basemap["config"]["url"] == "/grafana/project-zomboid-map/{z}/{x}/{y}.webp"
    assert basemap["config"]["minZoom"] == 11 and basemap["config"]["maxZoom"] == 17
    assert map_panel["gridPos"]["h"] == 20 and map_panel["options"]["view"]["zoom"] == 12.8
    assert panels["Warnings and Errors"]["gridPos"] == {"x": 0, "y": 46, "w": 12, "h": 12}
    assert all("name=~" in t["expr"] for t in map_panel["targets"])
    assert not any("player_lat" in t["expr"] or "player_lon" in t["expr"] for t in map_panel["targets"])
    caddy = (root / "src/roles/nixos/files/etc/nixos/modules/caddy.nix").read_text()
    assert "path /loki*" in caddy and "path /loki* /tempo*" in caddy
    assert "@project_zomboid_map path /grafana/project-zomboid-map/*" in caddy
    assert "forward_auth @project_zomboid_map http://127.0.0.1:3005" in caddy
    assert "uri /grafana/api/org" in caddy
    assert "handle_path /grafana/project-zomboid-map/*" in caddy
    assert "root * /var/lib/project-zomboid-map/tiles" in caddy
    assert dashboard["templating"]["list"][0]["name"] == "player"
    expressions = []
    for panel in dashboard["panels"]:
        if "datasource" not in panel:
            continue
        uid = panel["datasource"]["uid"]
        assert uid in ("mimir", "loki")
        for target in panel["targets"]:
            assert target["datasource"]["uid"] == uid
            expr = target["expr"]
            assert 'service="project-zomboid"' in expr and 'host="habiki"' in expr
            assert not re.search(r"\bor\s+(?:on\(\)\s+)?vector\(0\)", expr)
            expressions.append(expr)
    assert any('parameter="zombies-loaded"' in expr or 'zombies-(loaded|simulated|total)' in expr for expr in expressions)
    assert not any(re.search(r"node_(?:cpu|memory)_", expr) for expr in expressions)
    assert not any("health" in expr.lower() or "inventory" in expr.lower() for expr in expressions)
    assert 'folder      = grafana_folder.operations_services.uid' in terraform.split('resource "grafana_dashboard" "project_zomboid_service"')[1].split("}")[0]
    assert "/grafana/d/svc-project-zomboid/project-zomboid-server" in catalog["panels"][1]["options"]["content"]
    assert not any('resource "grafana_rule_group" "project_zomboid' in text for text in [terraform])
    print("PASS: dashboard UIDs, service labels, honest missing-data semantics, half-width player map and declarative registration")


if __name__ == "__main__":
    main(pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path("."))
