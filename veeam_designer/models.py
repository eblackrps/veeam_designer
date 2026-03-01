from dataclasses import dataclass, field
from typing import Dict, List, Optional
from .config import CONFIG


@dataclass
class VeeamInput:
    total_data_tb: float
    annual_growth_percent: float
    daily_change_percent: float

    backup_type: str
    primary_retention_days: int
    gfs_weekly_count: int
    gfs_monthly_count: int
    gfs_yearly_count: int

    backup_window_hours: float
    target_rpo_hours: float

    compression_ratio: float = CONFIG["compression_ratio_default"]
    dedupe_ratio: float = CONFIG["dedupe_ratio_default"]
    throughput_mb_per_core: float = CONFIG["throughput_mb_per_core"]
    read_write_overhead: float = CONFIG["read_write_overhead"]

    years_to_plan_for: int = CONFIG["years_to_plan_for"]

    vm_count: int = 0
    avg_vm_size_gb: float = 0.0

    wan_bandwidth_mbps: float = 0.0
    repo_type: str = "sobr"

    hypervisor: str = "vmware"
    has_san_access: bool = False
    on_host_proxy: bool = True


@dataclass
class RepoSizing:
    primary_repo_tb: float
    gfs_repo_tb: float
    total_repo_tb: float


@dataclass
class ProxySizing:
    proxy_count: int
    cores_per_proxy: int
    total_proxy_cores: int
    total_parallel_tasks: int
    required_throughput_mb_s: float


@dataclass
class BackupServerSizing:
    cores: int
    ram_gb: int


@dataclass
class HardenedRepoHost:
    count: int
    tb_per_host: float
    notes: str = ""


@dataclass
class GatewayServerSizing:
    count: int
    cores_each: int
    ram_gb_each: int
    notes: str = ""


@dataclass
class RolePlan:
    backup_server: BackupServerSizing
    proxies: ProxySizing
    hardened_repos: Optional[HardenedRepoHost] = None
    gateways: Optional[GatewayServerSizing] = None


@dataclass
class RiskScore:
    total_score: int
    level: str
    details: Dict[str, int] = field(default_factory=dict)


@dataclass
class SobrDesign:
    extent_count: int
    extent_size_tb: float
    capacity_tier_tb: float
    archive_tier_tb: float
    recommendation: str


@dataclass
class JobDefinition:
    name: str
    vm_count: int
    total_tb: float
    mode: str
    schedule: str
    repo_target: str


@dataclass
class JobSet:
    jobs: List[JobDefinition] = field(default_factory=list)


@dataclass
class RepoPerfModel:
    required_mb_s: float
    synthetic_full_mb_s: float
    notes: List[str] = field(default_factory=list)


@dataclass
class NetworkPlan:
    required_mbps: float
    achievable_rpo_hours: float
    meets_target: bool
    notes: List[str] = field(default_factory=list)


@dataclass
class CostEstimate:
    monthly_object_usd: float
    yearly_object_usd: float
    yearly_onprem_usd: float
    notes: List[str] = field(default_factory=list)


@dataclass
class Blueprint:
    role_plan: RolePlan
    jobs: JobSet
    sobr: SobrDesign
    repo_perf: RepoPerfModel
    network: NetworkPlan
    cost: CostEstimate
    notes: List[str] = field(default_factory=list)


@dataclass
class VeeamDesign:
    input: VeeamInput
    repo: RepoSizing
    roles: RolePlan
    jobs: JobSet
    sobr: SobrDesign
    repo_perf: RepoPerfModel
    network: NetworkPlan
    cost: CostEstimate
    blueprint: Blueprint
    risk: RiskScore
    notes: Dict[str, str]


@dataclass
class SiteDesign:
    name: str
    design: VeeamDesign


@dataclass
class MultiSiteDesign:
    sites: List[SiteDesign]
    total_repo_tb: float
    notes: Dict[str, str]
