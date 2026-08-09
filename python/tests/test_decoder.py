from hwm_solver.protocol.decoder import decode
def test_decoder():
 d=decode('t=000turns=>11:m013^luck^M007^mystery_blob','1');assert d.halfturn==11 and 7 in d.entity_hints and 'mystery_blob' in d.unknown and not d.training_safe
