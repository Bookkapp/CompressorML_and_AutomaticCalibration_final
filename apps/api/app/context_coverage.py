"""Small coverage matrix from frozen profiles; no source reads or fitting."""
from sqlalchemy import select
from .context_reference import profiles
from .context_review import review_state,active
from .context_storage import unpack,source_namespace
from .context_scope import coverage_rows
from .reference_jobs import ReviewConflict
from .context_reads import shared_read


def job_coverage(engine,job,who,settings):
    modules=(job.get("result") or {}).get("modules",[])
    if not modules: return {"job_id":job["job_id"],"modules":[]}
    if len(modules)>8: raise ReviewConflict("INVALID_MODULE_COVERAGE")
    ids=[m["profile_id"] for m in modules]
    with engine.connect() as conn:
        reviews={r["base_profile_id"]:dict(r) for r in conn.execute(select(review_state).where(
            review_state.c.base_profile_id.in_(ids),review_state.c.actor_id==who)).mappings()}
        chosen=[reviews.get(i,{}).get("reviewed_profile_id",i) for i in ids]
        pointers={r["module"]:dict(r) for r in conn.execute(select(active).where(active.c.machine_number==job["machine_number"])).mappings()}
    def read_summaries():
        summaries={}
        with engine.connect() as conn:
            for model_id,payload in conn.execute(select(profiles.c.profile_id,profiles.c.payload).where(profiles.c.profile_id.in_(chosen))):
                m=unpack(payload)
                if m["source_namespace"]!=source_namespace(settings): raise ReviewConflict("MODEL_OR_SOURCE_VERSION_CHANGED")
                summaries[model_id]={"module":m["module"],"states":coverage_rows(m),"future_validation":m.get("future_validation")}
        return summaries
    models=shared_read(("coverage-frozen-summaries",engine,tuple(chosen),source_namespace(settings)),read_summaries,ttl=300)
    result=[]
    for base_id,model_id in zip(ids,chosen):
        m=models.get(model_id)
        if m is None: raise ReviewConflict("MODEL_OR_SOURCE_VERSION_CHANGED")
        result.append({"module":m["module"],"profile_id":model_id,"base_profile_id":base_id,
                       "review_revision":reviews.get(base_id,{}).get("revision",0),
                       "active":pointers.get(m["module"],{}).get("profile_id")==model_id,
                       "states":m["states"],"future_validation":m.get("future_validation")})
    return {"job_id":job["job_id"],"machine_number":job["machine_number"],"modules":sorted(result,key=lambda r:r["module"])}
