import numpy as np
import pytest

from apps.api.app.fleet_assistance import FEATURES,IDENTITY_FIELDS,fit_local,pool,scores,transfer_gate,calibrate


def model(machine='017',n=80,offset=0):
    x=np.random.default_rng(17).normal(size=(n,6))+offset
    return fit_local(x,machine=machine,module=1,context='SV_OFF',reference_end='2026-08-15',
                     identity={k:'verified-test-contract' for k in IDENTITY_FIELDS},
                     evidence_status='REVIEWED_HEALTHY_REFERENCE')


def test_reject_entire_target_machine_and_future_donor():
    target=model();same={**model(),'module':3};future={**model('041'),'reference_end':'2026-08-16'}
    assert 'TARGET_MACHINE_EXCLUDED' in transfer_gate(target,same)['reasons']
    assert 'DONOR_AFTER_TARGET_CUTOFF' in transfer_gate(target,future)['reasons']


def test_missing_contracts_never_become_eligible_in_production():
    source={**model('041'),'identity':{},'evidence_status':'UNREVIEWED'}
    result=pool(model(),[source,model('058')])
    assert result['fleet_weight']==0 and not result['activation_eligible']
    assert any('REVIEWED_HEALTHY_REFERENCE_REQUIRED' in r['reasons'] for r in result['transfer_receipts'])


def test_relation_mismatch_and_level_mismatch_reject_transfer():
    target=model();source=model('041',offset=10)
    assert 'LEVEL_MISMATCH' in transfer_gate(target,source)['reasons']
    covariance=np.full((6,6),.99);np.fill_diagonal(covariance,1.)
    assert 'RELATIONSHIP_MISMATCH' in transfer_gate(target,{**model('058'),'covariance':covariance.tolist()})['reasons']


def test_sparse_target_cannot_certify_similarity():
    assert 'TARGET_SIMILARITY_UNCERTAIN' in transfer_gate(model(n=8),model('041'))['reasons']


def test_balanced_donors_no_duplicate_machine_weight():
    source=model('041');result=pool(model(),[source,source,model('058')])
    assert result['donor_machines']==['041','058']
    assert sum(r['eligible'] for r in result['transfer_receipts'])==2
    assert result['prior_strength']<=20 and 0<result['fleet_weight']<1
    assert np.isfinite(scores([[0]*6],result)).all()


def test_large_local_reference_reduces_fleet_influence():
    donors=[model('041'),model('058')]
    assert pool(model(n=40),donors)['fleet_weight']>pool(model(n=400),donors)['fleet_weight']


def test_sustained_wrong_level_remains_visible():
    target=model();assisted=pool(target,[model('041'),model('058')])
    assert scores([[10]*6]*20,assisted).min()>scores([[0]*6],assisted)[0]*10


def test_invalid_and_redundant_features_fail_explicitly():
    for values in [np.zeros((10,8)),np.full((10,6),np.nan)]:
        with pytest.raises(ValueError):fit_local(values,machine='017',module=1,context='SV_OFF',reference_end='2026-08-15')


def test_disjoint_threshold_calibration_and_constant_channel_stability():
    target=fit_local(np.zeros((30,6)),machine='017',module=1,context='SV_OFF',reference_end='2026-08-15')
    np.linalg.cholesky(target['covariance'])
    with pytest.raises(ValueError):calibrate(np.zeros((250,6)),target,start='2026-08-14',end='2026-08-22')
    calibrated=calibrate(np.zeros((250,6)),target,start='2026-08-15',end='2026-08-22')
    assert calibrated['threshold']==1 and list(FEATURES)==target['features']


def test_research_stratum_cannot_claim_activation_eligibility():
    target={**model(),'evidence_status':'UNREVIEWED','identity':{}}
    donors=[{**model(m),'identity':{},'evidence_status':'UNREVIEWED'} for m in ('041','058')]
    result=pool(target,donors,research=True)
    assert result['research_only'] and not result['activation_eligible']
    assert result['fleet_weight']>0


def test_relationship_sharing_preserves_local_levels_with_shifted_donors():
    target=model();donors=[model('041',offset=5),model('058',offset=-5)]
    assert pool(target,donors)['fleet_weight']==0
    relationship=pool(target,donors,parameter='relationship')
    assert relationship['fleet_weight']>0
    assert relationship['center']==target['center'] and relationship['scale']==target['scale']
    assert scores([[10]*6],relationship)[0]>scores([[0]*6],relationship)[0]*10
    with pytest.raises(ValueError):pool(target,donors,parameter='unverified-rule')
