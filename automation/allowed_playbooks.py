"""
Playbook allow-list — server-side security boundary.

EVERY call to POST /v1/automation/jobs validates the requested playbook
against this registry. Requests for unlisted playbooks are rejected with 403.

This is intentional defense-in-depth:
  - Prevents privilege escalation via playbook injection
  - The EDA rulebook can only trigger playbooks in this list
  - Adding a new playbook requires a code change + review, not just a rulebook edit

To add a playbook:
  1. Add the Ansible role/playbook under automation/
  2. Add the key + path here
  3. Deploy — the change is effective immediately on the next API restart
"""

ALLOWED_PLAYBOOKS: dict[str, str] = {
    "restart_service": "automation/playbooks/restart_service.yml",
    "disk_cleanup": "automation/playbooks/disk_cleanup.yml",
    "container_restart": "automation/playbooks/container_restart.yml",
    "linux_baseline": "automation/playbooks/linux_baseline.yml",
}
