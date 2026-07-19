from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[5]
K8S_ROOT = REPO_ROOT / "infra" / "k8s" / "base"


def _documents(path: str) -> list[dict[str, object]]:
    return [
        document
        for document in yaml.safe_load_all((K8S_ROOT / path).read_text())
        if isinstance(document, dict)
    ]


def test_kubernetes_base_includes_all_required_security_resources() -> None:
    kustomization = yaml.safe_load((K8S_ROOT / "kustomization.yaml").read_text())

    assert kustomization["namespace"] == "thesys"
    assert set(kustomization["resources"]) == {
        "namespace.yaml",
        "serviceaccounts.yaml",
        "workloads.yaml",
        "services.yaml",
        "network-policies.yaml",
        "disruption-budgets.yaml",
        "image-digest-policy.yaml",
    }


def test_kubernetes_workloads_are_least_privilege_and_separate_identities() -> None:
    deployments = _documents("workloads.yaml")

    assert {deployment["metadata"]["name"] for deployment in deployments} == {
        "thesys-api",
        "thesys-worker",
    }
    service_accounts = yaml.safe_load_all((K8S_ROOT / "serviceaccounts.yaml").read_text())
    assert {
        document["metadata"]["name"] for document in service_accounts if isinstance(document, dict)
    } == {"thesys-api", "thesys-worker"}
    for deployment in deployments:
        pod_spec = deployment["spec"]["template"]["spec"]
        assert pod_spec["serviceAccountName"] == deployment["metadata"]["name"]
        assert pod_spec["automountServiceAccountToken"] is False
        assert pod_spec["securityContext"] == {
            "runAsNonRoot": True,
            "runAsUser": 10001,
            "runAsGroup": 10001,
            "fsGroup": 10001,
            "seccompProfile": {"type": "RuntimeDefault"},
        }
        container = pod_spec["containers"][0]
        assert "@sha256:" in container["image"]
        assert container["securityContext"] == {
            "allowPrivilegeEscalation": False,
            "capabilities": {"drop": ["ALL"]},
            "readOnlyRootFilesystem": True,
        }
        assert container["resources"]["requests"]
        assert container["resources"]["limits"]
        assert {mount["mountPath"] for mount in container["volumeMounts"]} == {"/tmp"}


def test_kubernetes_network_and_admission_policies_fail_closed() -> None:
    policies = _documents("network-policies.yaml")
    policy_names = {policy["metadata"]["name"] for policy in policies}

    assert policy_names == {"default-deny", "api-ingress", "workload-egress"}
    default_deny = next(
        policy for policy in policies if policy["metadata"]["name"] == "default-deny"
    )
    assert default_deny["spec"] == {"podSelector": {}, "policyTypes": ["Ingress", "Egress"]}
    workload_egress = next(
        policy for policy in policies if policy["metadata"]["name"] == "workload-egress"
    )
    assert all("to" in egress for egress in workload_egress["spec"]["egress"])

    admission = _documents("image-digest-policy.yaml")
    assert {document["kind"] for document in admission} == {
        "ValidatingAdmissionPolicy",
        "ValidatingAdmissionPolicyBinding",
    }
    validation = admission[0]["spec"]["validations"][0]
    assert "@sha256" in validation["expression"]
