from math import ceil
from typing import List
from .models import VeeamInput, JobDefinition, JobSet
from .config import CONFIG


def build_jobs(vin: VeeamInput) -> JobSet:
    if vin.vm_count <= 0 or vin.avg_vm_size_gb <= 0:
        total_tb = vin.total_data_tb
        job = JobDefinition(
            name="Job-1",
            vm_count=0,
            total_tb=total_tb,
            mode=vin.backup_type,
            schedule="daily",
            repo_target=vin.repo_type,
        )
        return JobSet(jobs=[job])

    max_vms = CONFIG.get("max_vms_per_job", 50)
    max_tb = CONFIG.get("max_tb_per_job", 10.0)

    total_vms = vin.vm_count
    vm_size_tb = vin.avg_vm_size_gb / 1024.0
    total_tb = total_vms * vm_size_tb

    approx_jobs_by_vm = ceil(total_vms / max_vms)
    approx_jobs_by_tb = ceil(total_tb / max_tb)
    job_count = max(1, max(approx_jobs_by_vm, approx_jobs_by_tb))

    vms_per_job_base = total_vms // job_count
    remainder = total_vms % job_count

    jobs: List[JobDefinition] = []
    for i in range(job_count):
        vms_here = vms_per_job_base + (1 if i < remainder else 0)
        tb_here = vms_here * vm_size_tb
        jobs.append(
            JobDefinition(
                name=f"Job-{i + 1}",
                vm_count=vms_here,
                total_tb=round(tb_here, 2),
                mode=vin.backup_type,
                schedule="daily",
                repo_target=vin.repo_type,
            )
        )

    return JobSet(jobs=jobs)
