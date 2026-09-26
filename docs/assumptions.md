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

### Proxmox VE workers

Veeam Designer 5 sizes Proxmox VE workers from Veeam's task-based worker requirements instead of
reusing VMware proxy throughput assumptions:

- default worker: `6 vCPU`, `6 GB RAM`, `100 GB` disk
- default concurrency: `4 tasks` per worker
- each task above four adds `1 vCPU` and `1 GB RAM` to that worker
- one processing task is created for each protected VM
- host count, cluster count, desired concurrent tasks, and worker task limit are explicit inputs

For Hot-Add coverage, the calculator warns when the supplied Proxmox host count is greater than the
calculated worker count. Veeam best practice recommends at least one worker per Proxmox host when
Hot-Add is desired; VMs without a same-host worker can be processed over NBD.

References:

- [Veeam User Guide: Proxmox VE system requirements](https://helpcenter.veeam.com/docs/vbr/userguide/pve_system_requirements.html)
- [Veeam Best Practice Guide: Proxmox workers](https://bp.veeam.com/vbr/2_Design_Structures/D_Veeam_Components/D_backup_proxies/proxmox_workers.html)

### Nutanix AHV workers

AHV now uses its native worker model rather than the VMware proxy throughput table:

- default worker: `6 vCPU`, `6 GB RAM`, `100 GB` disk
- default concurrency: `4 tasks` per worker
- each task above four adds `1 vCPU` and `1 GB RAM`
- the calculator keeps at least one worker per supplied AHV cluster
- a warning is emitted if the calculated worker count exceeds the supplied host count

Veeam also recommends that total worker task limits in a cluster do not exceed the cluster physical
disk count. Veeam Designer does not yet collect AHV physical-disk count, so that check remains a
manual validation item.

References:

- [Veeam User Guide: AHV system requirements](https://helpcenter.veeam.com/docs/vbr/userguide/ahv_system_requirements.html)
- [Veeam User Guide: AHV worker sizing guidelines](https://helpcenter.veeam.com/docs/vbr/userguide/ahv_sizing_guide.html)

### Hyper-V backup proxies

Veeam's Best Practice Guide directs Hyper-V proxy sizing to the vSphere proxy sizing method. Veeam
Designer therefore sizes the aggregate Hyper-V proxy compute requirement from changed data,
backup-window throughput, and the virtual-proxy incremental baseline, then applies Hyper-V-specific
task and system-requirement floors:

- default throughput baseline: `80 MB/s` per core for incremental virtual-proxy processing
- optional `throughput_mb_per_core` remains available for environment-specific benchmark data
- no more than `2 concurrent tasks per CPU core`
- minimum `2 vCPU` per proxy/host allocation
- off-host memory meets both the Hyper-V minimum of `2 GB + 500 MB per task` and the vSphere
  planning allowance of up to `2 GB per core`
- on-host memory uses the stronger Hyper-V Best Practice allowance of up to `2 GB per running task`
- `300 MB` proxy disk footprint
- on-host designs distribute aggregate compute across the supplied Hyper-V host count
- off-host designs distribute aggregate compute across the requested task/proxy footprint

The vSphere throughput value is an adopted planning baseline rather than a Hyper-V-specific
performance guarantee. The Hyper-V Best Practice Guide explicitly points to the vSphere sizing
method, but environment benchmarking remains the preferred override for production designs.

References:

- [Veeam Best Practice Guide: Hyper-V proxy](https://bp.veeam.com/vbr/2_Design_Structures/D_Veeam_Components/D_backup_proxies/hyperv_proxies.html)
- [Veeam Best Practice Guide: Hyper-V backup modes](https://bp.veeam.com/vbr/Support/S_Hyper-V/backupmodes.html)
- [Veeam User Guide: Hyper-V backup proxy system requirements](https://helpcenter.veeam.com/docs/vbr/userguide/system_requirements_hv_proxy.html)
- [Veeam User Guide: limitation of concurrent tasks](https://helpcenter.veeam.com/docs/vbr/userguide/limiting_tasks.html)

### Veeam Infrastructure Appliance for VMware proxies

For VMware backup proxies, Veeam Designer can model either a managed Windows/Linux proxy or a
Veeam Infrastructure Appliance deployment. When Infrastructure Appliance is selected, the
calculator keeps proxy role resources separate from deployment allocation:

- proxy role cores continue to drive the throughput model
- each proxy allocation adds the Infrastructure Appliance baseline of `2 vCPU` and `8 GB RAM`
- each appliance includes a `120 GB` minimum system disk and `120 GB` minimum application-data disk
- the appliance overhead is not counted as additional proxy throughput capacity

This option is intentionally limited to VMware proxy sizing in the current calculator. Platform
workers are deployed by their virtualization plug-ins, and Hyper-V off-host proxies cannot be
assigned to Veeam Infrastructure Appliance.

References:

- [Veeam User Guide: Infrastructure Appliance system requirements](https://helpcenter.veeam.com/docs/vbr/userguide/system_requirements_via.html)
- [Veeam User Guide: VMware backup proxy system requirements](https://helpcenter.veeam.com/docs/vbr/userguide/system_requirements_vmware_proxy.html)

### Backup server

Backup server sizing follows the Veeam initial workload bands for VMware and physical-machine
backup environments:

- up to `500` workloads / `50` concurrent tasks: `12 vCPU`, `24 GB RAM`
- up to `1,000` workloads / `100` concurrent tasks: `24 vCPU`, `32 GB RAM`
- up to `5,000` workloads / `500` concurrent tasks: `48 vCPU`, `64 GB RAM`
- up to `10,000` workloads / `1,000` concurrent tasks: `56 vCPU`, `128 GB RAM`

Above that range, Veeam Designer extends the largest band linearly and marks the result as a
manual-review case.

The workload-band result is then checked against the current backup-server system requirements for
the selected deployment:

- both Windows and Linux-based backup servers require at least `16 GB RAM + 500 MB per concurrent job`
- Windows requires at least `8 vCPU`
- Veeam Software Appliance requires `8 vCPU`, with `6 vCPU / 16 GB RAM` sufficient for up to five workloads
- Veeam Software Appliance requires a minimum `240 GB` system disk and a second `240 GB`
  application-data disk
- Veeam documents larger SSD system-disk recommendations as protected workload count grows; the
  calculator reports the vendor minimum and leaves that capacity choice visible as an architecture
  review item rather than inventing a hard workload threshold for "small", "medium", or "large"

References:

- [Veeam Best Practice Guide: backup server sizing](https://bp.veeam.com/vbr/Support/configurations/backup_server.html)
- [Veeam User Guide: backup server system requirements](https://helpcenter.veeam.com/docs/vbr/userguide/system_requirements_backup_server.html)

### Repository retention, growth, and capacity

VM repository capacity is separated into retained backup data, operational headroom, and GFS
capacity instead of hiding all three inside one multiplier.

- annual source growth compounds over the configured planning horizon
- VBR 13 daily retention is modeled as N+1 days with a minimum of three restore points, assuming
  one successful restore point per day
- forever-forward and reverse-incremental chains are modeled as one retained full plus changed-data
  restore points
- weekly forward-incremental chains can retain up to six additional daily points at a chain
  boundary because an older chain is not deleted until the newer chain satisfies retention
- weekly synthetic fulls on ReFS/XFS use a Fast Clone changed-block planning model; exact physical
  use still depends on block-change locality
- active fulls and synthetic fulls without Fast Clone are modeled with the required retained full
  chains instead of receiving block-clone savings
- GFS points are reported as a conservative full-equivalent upper bound unless block-level change
  history is available

Disk repositories keep operational headroom separate from retained backup data. The default
transformation reserve is one full backup multiplied by the configured repo_overhead_factor
(1.25 by default). Extra room for an ad-hoc or one-off full is a separate architecture decision
because Veeam does not publish one universal amount that fits every repository and job design.

Immutability extends the effective retention window; the calculator does not add an arbitrary
metadata percentage. For a hardened repository, immutable chains must use forward incremental with
scheduled active or synthetic fulls. Forever-forward and reverse-incremental chains are rejected
for that combination. For object storage, block_generation_days remains an explicit planning
input because Veeam applies block generation automatically and the actual duration is
provider-dependent.

References:

- [Veeam Backup & Replication User Guide: retention policy](https://helpcenter.veeam.com/docs/vbr/userguide/retention_policy.html?ver=13)
- [Veeam Backup & Replication User Guide: hardened repository limitations](https://helpcenter.veeam.com/docs/vbr/userguide/hardened_repository_limitations.html?ver=13)
- [Veeam Best Practice Guide: repository storage](https://bp.veeam.com/vbr/2_Design_Structures/D_Veeam_Components/D_backup_repositories/repositories%20storage.html)

### Hardened repository host compute

Repository host compute follows Veeam repository guidance:

- 1 repository CPU core for every 3 proxy cores
- 4 GB RAM for each repository CPU core
- minimum host target of 2 cores and 8 GB RAM

The calculator also keeps the repository host count capped by configured per-host capacity and
preserves separate notes for large ReFS/XFS filesystem footprints.

Reference:

- [Veeam Best Practice Guide: backup repositories](https://bp.veeam.com/vbr/2_Design_Structures/D_Veeam_Components/D_backup_repositories/)

### Replication and CDP

Replication bandwidth is modeled as the average raw changed-data rate required to avoid backlog.
RPO controls recovery-point cadence and latency tolerance; it does not multiply or divide the
average number of changed bytes produced per day. Replica capacity is the source VM footprint.
Additional standard-replication restore-point deltas are not guessed because replica retention is
not currently an input.

CDP keeps RPO and short-term retention as independent inputs:

- supported CDP RPO input range is 2 seconds through 60 minutes
- short-term retention capacity is based on changed data over cdp_retention_hours
- the capacity model includes Veeam's documented allowance that retention can consume up to 25%
  longer during chain transformation
- CDP proxy sizing uses measured cluster write I/O when cdp_write_io_mb_s is supplied
- when measured write I/O is absent, proxy sizing falls back to average changed-data throughput and
  labels that result as a planning assumption
- each CDP proxy is planned with at least 50 GB of disk-based write-I/O cache
- network-encryption proxy tiers are kept separate from non-encrypted throughput tiers

### WAN accelerator

WAN accelerator mode is explicit and does not inherit repository compression or deduplication
ratios.

- auto selects Low bandwidth mode at 1-100 Mbps and Direct above 100 Mbps
- High bandwidth mode must be selected explicitly for the high-latency/high-change cases where it
  is appropriate
- Low mode uses 2% source/target digest planning and global cache
- High mode uses 1% digest planning and no global cache
- Low-mode target cache is at least 40 GB, can be explicitly increased, and also honors Veeam's
  10 GB per unique guest-OS-type guidance when that count is supplied
- approximately 500 Mbps per target accelerator is used as the published processing-envelope
  planning value for multiple pairs

The automatic VM path uses neutral 1.0 WAN reduction ratios. If a project explicitly supplies a
nested wan_accel input with compression or deduplication ratios, those values are treated as
workload planning assumptions, not guaranteed Veeam reduction factors.

References:

- [Veeam Backup & Replication User Guide: system requirements](https://helpcenter.veeam.com/docs/vbr/userguide/system_requirements.html?ver=13)
- [Veeam Best Practice Guide: WAN Accelerator](https://bp.veeam.com/vbr/2_Design_Structures/D_Veeam_Components/D_Wan_accelerator/WAN_Accelerator.html)
- [Veeam Best Practice Guide: WAN accelerators](https://bp.veeam.com/vbr/3_Build_structures/B_Veeam_Components/B_wan_accelerators/Wan_Accelerators.html)

### NAS / unstructured workloads

NAS calculations distinguish repository capacity, general-purpose proxy resources, and cache
repository resources.

- compress_pct is an explicit data-reduction input; no reduction percentage is invented
- annual growth compounds over the configured forecast horizon
- disk-backed capacity uses the conservative formula-table values on the Veeam Best Practice page:
  backup data plus 10% metadata and 10% workspace
- the same Best Practice page contains worked examples using 5% metadata and 5% workspace; the
  calculator deliberately uses the more conservative table values and calls out that
  documentation inconsistency
- direct-to-object capacity adds 5% metadata and no workspace reserve
- direct-to-object cache disk reserves at least 1 GB of active metadata per 1 million file
  versions per protecting job; with only aggregate file count available, the calculator assumes
  one active version per file and one protecting job
- general-purpose proxy processing uses Veeam's 100 MB/s / approximately 0.34 TB/h starting
  point, 5 million files/hour/task, two tasks per core, and 1.33 GB RAM per core/task, then
  applies current system minimums
- concurrent_sources is explicit and drives cache-repository compute sizing
- NAS short-term retention is incremental-forever; weekly/monthly/yearly GFS counts are not turned
  into fabricated full-backup capacity

References:

- [Veeam Best Practice Guide: NAS cache repository](https://bp.veeam.com/vbr/2_Design_Structures/D_Veeam_Components/D_backup_repositories/nascache.html)
- [Veeam Best Practice Guide: NAS backup repository](https://bp.veeam.com/vbr/2_Design_Structures/D_Veeam_Components/D_backup_repositories/nasrepo.html)
- [Veeam Best Practice Guide: general-purpose backup proxy](https://bp.veeam.com/vbr/2_Design_Structures/D_Veeam_Components/D_backup_proxies/general_purpose_proxy.html)
- [Veeam Best Practice Guide: unstructured backup proxy](https://bp.veeam.com/vbr/3_Build_structures/B_Veeam_Components/B_backup_proxies/unstructured_backup_proxy.html)

### Physical / Agent workloads

Managed Agent capacity follows the same VBR 13 N+1 daily-retention rule with a three-restore-point
minimum. The model does not invent an Agent compression or deduplication ratio.

Operational headroom is separated from retained data. The transformation reserve is one full
backup multiplied by the configured repo_overhead_factor; additional one-off-full headroom remains
a separate planning decision.

General-purpose proxy resources are driven by the explicit concurrent-task input and current proxy
minimums. The legacy payload fields coordinator_cores and coordinator_ram_gb are retained for API
compatibility, but the UI and documentation identify those resources as the general-purpose proxy.

Reference:

- [Veeam Backup & Replication User Guide: Agent retention](https://helpcenter.veeam.com/docs/vbr/userguide/agents_retention.html?ver=13)

### Tape

Tape sizing is capacity-first and assumption-explicit.

- built-in native capacities are 6 TB for LTO-7, 12 TB for LTO-8, and 18 TB for LTO-9
- LTO-10 requires an explicit native_capacity_tb because current media specifications are not a
  single unambiguous native-capacity value
- media compression defaults to 1.0:1; a higher value is used only when the project supplies it
- drive count is calculated from an explicit write window and per-drive native throughput; without
  those inputs the result is one functional minimum, not a fabricated performance estimate
- cartridge counts cover data capacity only; scratch media, cleaning cartridges, rotation sets,
  GFS media pools, and spare slots are policy inputs and are not invented
- media cost is calculated only when cost_per_cartridge_usd is explicitly supplied

### Veeam ONE and Enterprise Manager

Veeam ONE uses the current published backup-data monitoring workload ranges. The calculator takes
the conservative upper end of the applicable published range and adds the documented connected-VBR
overhead.

For deployments at or below 1,000 protected workloads, the calculator preserves the documented
all-in-one minimum of 4 vCPU / 8 GB RAM rather than interpolating below it.

Database capacity is intentionally not inferred from a made-up MB-per-workload rate. The result
directs operators to the official Veeam ONE Database Calculator for SQL application-data sizing.
Enterprise Manager uses the current recommended Linux-appliance resources. VSPC is treated as a
separate product and is not sized from an arbitrary tenant-to-CPU ratio.

### Licensing

Licensing output is consumption planning, not commercial quoting.

- generic VM, physical, and cloud workload counts are treated as one instance each in the
  instance-license planner, subject to entitlement-specific exceptions
- unstructured instance licensing is estimated at one instance per 500 GB, rounded down; Veeam
  performs that rounding per data source, so an aggregate estimate can differ from a source-level
  inventory
- capacity licensing uses 1 TB chunks, rounded down per protected source; the calculator exposes
  the aggregate planning estimate and calls out the limitation
- socket licensing requires the actual occupied motherboard sockets on protected source hosts;
  VM count is never converted into sockets
- commercial price, renewal, discount, edition, package, and maintenance figures are not inferred

### Object storage and capacity tier

Generic object targets and Direct-to-Object designs are treated as object-storage targets across
repository, SOBR, performance, and cost calculations. Direct-object designs do not receive
disk-repository transformation headroom or Fast Clone assumptions.

The calculator rejects reverse incremental and an independently scheduled weekly synthetic-full
mode for direct object targets. For SOBR Capacity Tier, Copy, Move, and Copy + Move are modeled as
different policies:

- Copy places the modeled retained short-term/GFS backup footprint in object storage immediately
  while preserving the full local performance-tier footprint.
- Move considers only restore points in inactive chains. The calculator uses
  capacity_tier_operational_restore_days as the Veeam operational restore window and does not use a
  percentage offload shortcut.
- Copy + Move keeps the Copy object footprint while removing from local storage only the short-term
  data that the Move model identifies as older than the operational restore window.

For weekly forward-incremental chains, the model uses a conservative steady-state phase in which the
newest seven daily restore points remain the active chain. Older points are considered sealed; only
sealed points strictly older than the operational restore window are eligible for Move. For weekly
synthetic fulls on ReFS/XFS, local reclaim credit is limited to changed-block size because Fast
Clone fulls can share blocks still referenced by the active chain. For active fulls and non-Fast
Clone synthetic fulls, eligible full and incremental files are counted at their modeled physical
sizes.

Veeam documents that forever-forward incremental normally has no inactive chain, so Move is ignored
and Copy behavior applies. GFS can create synthetic fulls that make such chains inactive, but the
current GFS inputs are counts rather than dated schedules. The calculator therefore does not claim
additional GFS Move savings without explicit age data. Reverse-incremental Move savings are also not
credited because the model does not define a periodic full event that proves an inactive chain.

Operational transformation headroom is always kept local and is never treated as Capacity Tier
data. GFS capacity is conservatively kept local for Move-only sizing unless its age is explicit.

Object First appliance node count is not inferred from a generic object target. Current Ootbi
hardware is available in multiple usable-capacity models, so the optional helper requires an
explicit node capacity and adds no fabricated immutability percentage.

Object-storage role planning does not automatically create a hardened repository host or gateway.
Veeam supports direct data-mover access to object storage as well as gateway-mediated access; the
calculator does not invent that topology without an explicit project input.

References:

- [Veeam: Add Capacity Tier](https://helpcenter.veeam.com/docs/vbr/userguide/new_capacity_tier.html?ver=13)
- [Veeam: Moving Backups to Capacity Tier](https://helpcenter.veeam.com/docs/vbr/userguide/capacity_tier_move.html?ver=13)
- [Veeam: Copying Backups to Capacity Tier](https://helpcenter.veeam.com/docs/vbr/userguide/capacity_tier_copy.html?ver=13)
- [Veeam: Backup Chain Detection](https://helpcenter.veeam.com/docs/vbr/userguide/capacity_tier_inactive_backup_chain.html?ver=13)
- [Veeam: Capacity Tier Data Transfer](https://helpcenter.veeam.com/docs/vbr/userguide/capacity_tier_data_transfer.html?ver=13)

### Cost planning

Storage cost output is driven by explicit per-site planning rates:

- object_cost_usd_per_tb_month is the modeled effective object-storage cost per TB per month
- onprem_cost_usd_per_tb_year is the modeled effective local-storage cost per TB per year

Capacity Tier cost uses the capacity footprints produced by the policy model above. There is no
provider-price lookup, percentage offload estimate, or inferred cloud break-even point.

These rates are not Veeam pricing or live provider quotes. The storage-rate model does not infer
provider-specific API charges, retrieval/egress, minimum-storage-duration charges, taxes, hardware
purchase cost, support, power, rack space, discounts, or cloud break-even. Use a fully burdened
local-storage rate and an effective object-storage rate if those costs need to be represented.

When Capacity Tier Object Lock is enabled, the object-storage dollar amount is a **base modeled
footprint**, not a prediction of the provider's final billed occupancy. Veeam removes immutable
Capacity Tier blocks only after their immutability period expires. Veeam also applies Block
Generation automatically: 30 days for Amazon S3, IBM Cloud, Google Cloud, and 11:11 Cloud object
storage, and 10 days for other object-storage repositories. Reused or dependent blocks can have
their immutability extended into later generations.

Because that carryover depends on block age, chain behavior, immutability settings, GFS behavior,
repository type, and provider billing, Veeam Designer does not invent a percentage uplift. Actual
billed object storage can exceed the calculator's base footprint while expired blocks remain
immutable.

References:

- [Veeam: Retention Policy for Capacity Tier](https://helpcenter.veeam.com/docs/vbr/userguide/capacity_tier_retention.html?ver=13)
- [Veeam: Block Generation](https://helpcenter.veeam.com/docs/vbr/userguide/block_gen.html?ver=13)
- [Veeam: Object Storage Immutability Considerations](https://helpcenter.veeam.com/docs/vbr/userguide/os_immutability_limitations.html?ver=13)

## Remaining Planning Assumptions

The following values still require engineering judgment or environment-specific evidence:

- mixed-environment proxy throughput reuses the VMware transport table unless a custom
  throughput_mb_per_core benchmark is supplied
- NBD proxy throughput remains a conservative planning heuristic
- Fast Clone repository capacity uses a changed-block model because exact physical savings require
  block-level history
- GFS capacity uses a conservative full-equivalent upper bound when block-level history is absent
- CDP proxy sizing falls back to average changed-data rate when measured cluster write I/O is not
  supplied
- configured infrastructure-cost rates are assumptions, not quotes

## Custom Overrides

The optional `throughput_mb_per_core` field is still supported in YAML, JSON, and CLI workflows as
an advanced override. Use it only when you have transport-specific benchmark data for your
environment. The web UI labels this as a custom override so it does not look like part of the
default calibrated calculator path.
