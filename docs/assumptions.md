# Sizing Assumptions

This document records the sizing rules that Veeam Designer currently applies and how they map to
official Veeam guidance.

## Scope

Veeam Designer is a planning calculator. It is not a vendor-certified sizing service, and it does
not replace environment-specific validation with Veeam architects, performance testing, or current
system-requirements reviews.

The codebase now separates two categories:

- `Calibrated formulas`: rules derived directly from published Veeam guidance
- `Documented heuristics`: rules retained as practical planning assumptions where Veeam does not
  publish a direct formula that maps cleanly to this UI

## Calibrated Formulas

### VMware backup proxies

Veeam Designer sizes VMware backup proxies from Veeam transport guidance for incremental backup
throughput:

- virtual proxy to block target: about `80 MB/s` per CPU core
- virtual proxy to object target: about `80 MB/s` per CPU core
- physical proxy with Direct SAN to block target: about `250 MB/s` per CPU core
- physical proxy with Direct SAN to object target: about `150 MB/s` per CPU core
- NBD is modeled conservatively as a documented calculator heuristic because Veeam does not publish
  a dedicated per-core NBD table in the same sizing guide

The calculator also keeps the Veeam best-practice target of `2 proxy tasks per CPU core` and
recommends at least `2 proxy servers` per site for production availability.

Reference:

- [Veeam Best Practice Guide: VMware proxy sizing](https://bp.veeam.com/vbr/Support/configurations/vmware_proxy.html)

### Backup server

Backup server sizing follows the Veeam initial workload bands for VMware and physical-machine
backup environments:

- up to `500` workloads / `50` concurrent tasks: `12 vCPU`, `24 GB RAM`
- up to `1,000` workloads / `100` concurrent tasks: `24 vCPU`, `32 GB RAM`
- up to `5,000` workloads / `500` concurrent tasks: `48 vCPU`, `64 GB RAM`
- up to `10,000` workloads / `1,000` concurrent tasks: `56 vCPU`, `128 GB RAM`

Above that range, Veeam Designer extends the largest band linearly and marks the result as a
manual-review case.

Reference:

- [Veeam Best Practice Guide: backup server sizing](https://bp.veeam.com/vbr/Support/configurations/backup_server.html)

### Hardened repository host compute

Repository host compute follows Veeam repository guidance:

- `1` repository CPU core for every `3` proxy cores
- `4 GB RAM` for each repository CPU core
- minimum host target of `2 cores` and `8 GB RAM`

The calculator also keeps the repository host count capped by configured per-host capacity and
preserves separate notes for large ReFS/XFS filesystem footprints.

Reference:

- [Veeam Best Practice Guide: backup repositories](https://bp.veeam.com/vbr/2_Design_Structures/D_Veeam_Components/D_backup_repositories/)

### WAN accelerator

WAN accelerator sizing follows Veeam low-bandwidth guidance:

- source digest space is sized at `20 GB` per `1 TB` of protected source data
- target digest space is sized at up to `2%` of protected source data when digest recalculation is
  required
- target global cache is modeled at `100 GB` per connected source accelerator in the current UI.
  Veeam also publishes an OS-count-based formula for low-bandwidth mode, but the UI does not
  currently collect unique guest OS counts.
- the calculator uses `500 Mbps` per target accelerator as the planning envelope for multiple
  accelerator pairs

The automatic VM-to-WAN calculator path now sends projected source size and daily change rate into
the WAN model so future-growth planning stays aligned with the rest of the VM workflow.

References:

- [Veeam Backup & Replication User Guide: system requirements](https://helpcenter.veeam.com/docs/vbr/userguide/system_requirements.html?ver=13)
- [Veeam Best Practice Guide: WAN Accelerator](https://bp.veeam.com/vbr/2_Design_Structures/D_Veeam_Components/D_Wan_accelerator/WAN_Accelerator.html)
- [Veeam Best Practice Guide: WAN accelerators](https://bp.veeam.com/vbr/3_Build_structures/B_Veeam_Components/B_wan_accelerators/Wan_Accelerators.html)

### NAS / unstructured workloads

NAS sizing follows Veeam unstructured-data guidance in the following ways:

- file proxy throughput uses `100 MB/s` per CPU core as the planning baseline
- file inventory scanning uses `5 million files per hour` per CPU core as the alternate bottleneck
- object-storage cache repository sizing reserves `5%` of source capacity
- NAS long-term retention is treated as `incremental-forever`, so weekly, monthly, and yearly GFS
  counts are not separately added to repository capacity

For disk-backed NAS targets, Veeam Designer does not add a separate synthetic cache-repository disk
reservation because Veeam documents that this footprint is usually small enough not to drive
dedicated sizing.

References:

- [Veeam Best Practice Guide: NAS cache repository](https://bp.veeam.com/vbr/2_Design_Structures/D_Veeam_Components/D_backup_repositories/nascache.html)
- [Veeam Best Practice Guide: NAS backup repository](https://bp.veeam.com/vbr/2_Design_Structures/D_Veeam_Components/D_backup_repositories/nasrepo.html)
- [Veeam Best Practice Guide: general-purpose backup proxy](https://bp.veeam.com/vbr/2_Design_Structures/D_Veeam_Components/D_backup_proxies/general_purpose_proxy.html)
- [Veeam Best Practice Guide: unstructured backup proxy](https://bp.veeam.com/vbr/3_Build_structures/B_Veeam_Components/B_backup_proxies/unstructured_backup_proxy.html)

## Documented Heuristics

These paths remain heuristics in the current release and are labeled that way in code, notes, or
tests:

- Hyper-V, AHV, and mixed-environment proxy throughput still reuse the VMware transport table
  unless you provide a custom `throughput_mb_per_core` override
- NBD proxy throughput is intentionally conservative rather than source-table-driven
- VM repository capacity still uses the existing weekly-full plus incremental planning model used by
  this app
- CDP proxy sizing remains a simplified workload-driven estimate
- Veeam ONE sizing remains a practical tiered heuristic
- licensing and cost outputs remain configuration-driven planning estimates, not live pricing

## Custom Overrides

The optional `throughput_mb_per_core` field is still supported in YAML, JSON, and CLI workflows as
an advanced override. Use it only when you have transport-specific benchmark data for your
environment. The web UI labels this as a custom override so it does not look like part of the
default calibrated calculator path.
