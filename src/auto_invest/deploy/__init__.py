"""Deploy automation package — spec 006.

Public surface (what we ship in this branch):
    KernelManifest       — pydantic-validated load of .specify/memory/kernel.toml
    KernelTouchReport    — result of kernel_diff_check()
    load_kernel_manifest — parse the manifest file
    kernel_diff_check    — given a list of changed paths, return KernelTouchReport

Spec 006's full deploy runner (pull / sync / migrate / health-check /
rollback orchestration) is staged but not yet shipped here; the
kernel-touch guard is shipped first because constitution IX.B-1
requires it on the critical path of any deploy, autonomous or human.
"""

from auto_invest.deploy.kernel_guard import (
    KernelGroupTouch,
    KernelManifest,
    KernelManifestError,
    KernelTouchReport,
    kernel_diff_check,
    load_kernel_manifest,
)

__all__ = [
    "KernelGroupTouch",
    "KernelManifest",
    "KernelManifestError",
    "KernelTouchReport",
    "kernel_diff_check",
    "load_kernel_manifest",
]
