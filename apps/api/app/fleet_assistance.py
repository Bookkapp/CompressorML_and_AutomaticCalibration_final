"""Frozen, selective Fleet assistance. Numerical screening never certifies health.

Six physical coordinates avoid exact DP linear dependencies. Fleet priors are
estimated from asset summaries (Empirical Bayes), with bounded prior strength.
Caller supplies disjoint reference/calibration data; no online adaptation.
"""
from __future__ import annotations

import numpy as np
from scipy.linalg import solve_triangular

VERSION = "selective-fleet-empirical-bayes-v1"
FEATURES = ("hp1", "lp1", "hp2", "lp2", "temphi", "templo")
IDENTITY_FIELDS = ("hardware", "module_role", "configuration", "control_contract",
                   "pressure_basis", "temperature_unit", "service_epoch")


def _matrix(values):
    x = np.asarray(values, dtype=float)
    if x.ndim != 2 or x.shape[1] != len(FEATURES) or not np.isfinite(x).all():
        raise ValueError("six complete finite physical coordinates required")
    return x


def robust_location(values):
    x = _matrix(values)
    center = np.median(x, axis=0)
    scale = np.maximum(.1, np.maximum(1.4826 * np.median(np.abs(x-center), axis=0),
                     (np.quantile(x,.75,axis=0)-np.quantile(x,.25,axis=0))/1.349))
    return center, scale


def fit_local(values, *, machine, module, context, reference_end, identity=None,
              evidence_status="UNREVIEWED", sample_minutes=15):
    """Input must already be chronological, gap-aware thinned Reference points.

    Thinning reduces serial dependence; it is not a claim of iid observations.
    Robust clipping affects fit only, never raw evidence or future scores.
    """
    x = _matrix(values)
    if len(x) < 8:
        raise ValueError("at least eight Reference observations required")
    center, scale = robust_location(x)
    z = np.clip((x-center)/scale, -6., 6.)
    scatter = z.T @ z / len(z)
    # Fixed mild diagonal shrinkage; invert via Cholesky, never raw inverse.
    correlation = .9 * scatter + .1 * np.diag(np.diag(scatter))
    covariance = correlation * np.outer(scale,scale) + np.diag((scale*.05)**2)
    return {"version":VERSION,"features":list(FEATURES),"machine":str(machine),
            "module":int(module),"context":context,"reference_end":reference_end,
            "identity":identity or {},"evidence_status":evidence_status,"n":len(x),
            "sample_minutes":sample_minutes,"center":center.tolist(),"scale":scale.tolist(),
            "covariance":covariance.tolist(),"fit_clipped_points":int(np.any(np.abs((x-center)/scale)>6,axis=1).sum()),
            "approximation":"robust moments and thinned dependent observations; not exact iid NIW inference"}


def _correlation(covariance):
    covariance=np.asarray(covariance,float)
    std=np.sqrt(np.maximum(np.diag(covariance),1e-10))
    return covariance/np.outer(std,std)


def transfer_gate(local, donor, *, research=False, parameter="joint"):
    if parameter not in {"joint","relationship"}:raise ValueError("unsupported sharing parameter")
    reasons=[]
    if donor["machine"]==local["machine"]: reasons.append("TARGET_MACHINE_EXCLUDED")
    if donor["context"]!=local["context"]: reasons.append("CONTROL_CONTEXT_MISMATCH")
    if donor["reference_end"]>local["reference_end"]: reasons.append("DONOR_AFTER_TARGET_CUTOFF")
    if tuple(donor.get("features",[]))!=FEATURES: reasons.append("FEATURE_CONTRACT_MISMATCH")
    if research:
        # A controlled hypothesis, not a verified hardware/role mapping.
        if donor["module"]!=local["module"]: reasons.append("EXPERIMENT_MODULE_STRATUM_MISMATCH")
    else:
        if local.get("evidence_status")!="REVIEWED_HEALTHY_REFERENCE" or donor.get("evidence_status")!="REVIEWED_HEALTHY_REFERENCE":
            reasons.append("REVIEWED_HEALTHY_REFERENCE_REQUIRED")
        for field in IDENTITY_FIELDS:
            left,right=local.get("identity",{}).get(field),donor.get("identity",{}).get(field)
            if not left or not right: reasons.append(f"UNVERIFIED_{field.upper()}")
            elif left!=right: reasons.append(f"MISMATCH_{field.upper()}")
    if local["n"]<20: reasons.append("TARGET_SIMILARITY_UNCERTAIN")
    scale=np.maximum(np.asarray(local["scale"]),np.asarray(donor["scale"]))
    displacement=(np.asarray(local["center"])-donor["center"])/scale
    center_distance=float(np.sqrt(np.mean(displacement**2)))
    corr_distance=float(np.linalg.norm(_correlation(local["covariance"])-_correlation(donor["covariance"]),ord="fro")/np.sqrt(30))
    if parameter=="joint" and center_distance>1.5: reasons.append("LEVEL_MISMATCH")
    if corr_distance>.5: reasons.append("RELATIONSHIP_MISMATCH")
    return {"eligible":not reasons,"reasons":reasons,"center_distance":center_distance,
            "correlation_distance":corr_distance,"sharing_parameter":parameter,
            "mode":"RESEARCH_ONLY" if research else "VERIFIED_REFERENCE"}


def pool(local, donors, *, research=False, parameter="joint"):
    """One donor summary per machine; target entire machine is always excluded."""
    receipts=[];accepted=[];seen=set()
    for donor in donors:
        gate=transfer_gate(local,donor,research=research,parameter=parameter)
        if gate["eligible"] and donor["machine"] in seen:
            gate={**gate,"eligible":False,"reasons":["DUPLICATE_DONOR_MACHINE"]}
        receipts.append({"machine":donor["machine"],"module":donor["module"],**gate})
        if gate["eligible"]:
            seen.add(donor["machine"]);accepted.append(donor)
    result={**local,"transfer_receipts":receipts,"donor_machines":sorted(seen),
            "research_only":research,"fleet_weight":0.,"prior_strength":0.,
            "activation_eligible":False,"assessment":"LOCAL_ONLY","sharing_parameter":parameter}
    if len(accepted)<2:
        result["pooling_reason"]="AT_LEAST_TWO_COMPATIBLE_DONOR_MACHINES_REQUIRED"
        return result
    if parameter=="relationship":
        # Share only dimensionless covariance shape. Frozen Local mean and
        # channel scales remain the target's; donor levels cannot move them.
        correlations=np.asarray([_correlation(d["covariance"]) for d in accepted])
        average=np.mean(correlations,axis=0)
        dispersion=float(np.mean(np.var(correlations,axis=0)))
        strength=float(np.clip(1./max(dispersion,.05),1.,20.))
        n=local["n"];local_cov=np.asarray(local["covariance"])
        std=np.sqrt(np.diag(local_cov));prior_cov=average*np.outer(std,std)
        dimension=len(FEATURES);nu0=dimension+2.+strength
        degrees=nu0+n-dimension+1.
        psi=(nu0-dimension-1.)*prior_cov+n*local_cov
        predictive=psi*(n+1.)/(n*degrees)
        np.linalg.cholesky(predictive)
        result.update(covariance=predictive.tolist(),prior_strength=strength,
                      fleet_weight=(strength+1.)/(n+strength+1.),predictive_df=degrees,
                      assessment="FLEET_RELATIONSHIP_PROPOSAL",pooling_reason="LOCAL_LEVEL_FIXED_SELECTIVE_RELATIONSHIP_SHARING")
        return result
    centers=np.asarray([d["center"] for d in accepted]);mu0=np.median(centers,axis=0)
    within=np.mean([d["covariance"] for d in accepted],axis=0)
    between=(centers-mu0).T@(centers-mu0)/len(centers)
    # Asset-balanced moments; κ is a capped EB estimate, not a day-count rule.
    ratio=float(np.median(np.diag(within)/np.maximum(np.diag(between),.01)))
    kappa=float(np.clip(ratio,1.,20.))
    dimension=len(FEATURES);nu0=dimension+2.+kappa
    psi0=(nu0-dimension-1.)*(within+between)
    n=local["n"];mean=np.asarray(local["center"]);delta=mean-mu0
    posterior_mean=(kappa*mu0+n*mean)/(kappa+n)
    psi=psi0+n*np.asarray(local["covariance"])+(kappa*n/(kappa+n))*np.outer(delta,delta)
    degrees=nu0+n-dimension+1.
    predictive=psi*(kappa+n+1.)/((kappa+n)*degrees)
    predictive=(predictive+predictive.T)/2+np.diag(np.maximum(np.diag(within),.01)*1e-8)
    np.linalg.cholesky(predictive)
    result.update(center=posterior_mean.tolist(),covariance=predictive.tolist(),
                  prior_strength=kappa,fleet_weight=kappa/(kappa+n),predictive_df=degrees,
                  assessment="FLEET_ASSISTED_PROPOSAL",pooling_reason="COMPATIBLE_REFERENCE_SUMMARIES")
    return result


def scores(values, model):
    x=_matrix(values);delta=x-np.asarray(model["center"])
    chol=np.linalg.cholesky(np.asarray(model["covariance"]))
    whitened=solve_triangular(chol,delta.T,lower=True,check_finite=False)
    return np.sum(whitened**2,axis=0)


def self_scores(values, local):
    return np.max(np.abs((_matrix(values)-local["center"])/local["scale"]),axis=1)


def calibrate(values, model, *, start, end):
    if start<model["reference_end"] or end<=start:
        raise ValueError("calibration must be disjoint and after Reference")
    x=_matrix(values)
    if len(x)<200: raise ValueError("threshold calibration requires at least 200 observations")
    return {**model,"threshold":float(max(1.,np.quantile(scores(x,model),.995))),
            "threshold_period":[start,end],"threshold_points":len(x),
            "threshold_method":"disjoint historical calibration Q99.5; strict greater-than; not fault probability"}
