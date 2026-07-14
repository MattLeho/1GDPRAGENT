import pytest
from privacy.wording import ClaimBasis,guarded_statement

@pytest.mark.parametrize("basis,prefix",[
 (ClaimBasis.OBSERVED,"available export evidence indicates"),
 (ClaimBasis.CONTROLLER_ASSIGNED,"appears controller-assigned"),
 (ClaimBasis.TECHNICAL_POSSIBILITY,"the combination could technically support"),
 (ClaimBasis.PURPOSE_DISTANCE,"possible purpose drift"),
 (ClaimBasis.UNKNOWN,"no source evidence currently establishes"),
])
def test_preferred_epistemic_prefixes(basis,prefix):
    assert guarded_statement("A location pattern is present",basis=basis).startswith(prefix)

@pytest.mark.parametrize("text",["You are depressed","Controller knows for certain","This is illegal",
                                  "They are abusing data","The identifier will survive deletion"])
def test_unsupported_certainty_and_legal_language_is_rejected(text):
    with pytest.raises(ValueError): guarded_statement(text,basis=ClaimBasis.UNKNOWN)
