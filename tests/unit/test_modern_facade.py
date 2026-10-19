import pytest

from exterior_agent.domain.validate import TOL, parse_project
from exterior_agent.geometry.modern_facade import facade_objects


@pytest.fixture
def objects(modern_data):
    return {o.name: o for o in facade_objects(parse_project(modern_data))}


def b(obj):
    return obj.mesh.bounds()


def test_balcony_slab_and_rail(objects):
    slab, rail = objects["Balcony_F2"], objects["Balcony_F2_Rail"]
    assert slab.collection == rail.collection == "Balconies"
    lo, hi = b(slab)
    assert (lo[0], hi[0], lo[1], hi[1], hi[2]) == pytest.approx((-2.0, 2.0, 3.5, 4.5, 3.6), abs=TOL)
    rlo, rhi = b(rail)
    assert rhi[2] == pytest.approx(4.7, abs=TOL) and rlo[2] == pytest.approx(3.6, abs=TOL)
    assert (rlo[0], rhi[0], rlo[1]) == pytest.approx((-2.0, 2.0, 3.5), abs=TOL)
    assert rail.material == "MAT_Glass" and len(rail.mesh.faces) == 3 * 6


def test_frame_is_inverted_u(objects):
    frame = objects["Frame_F2-2"]
    assert frame.collection == "Facade" and frame.material == "MAT_Frame"
    lo, hi = b(frame)
    assert (lo[0], hi[0], lo[1], hi[1]) == pytest.approx((-2.5, 2.5, 4.1, 4.5), abs=TOL)
    assert (lo[2], hi[2]) == pytest.approx((3.6, 6.9), abs=TOL)
    assert len(frame.mesh.faces) == 3 * 6  # two posts + top beam


def test_louvers_evenly_spaced(objects):
    louvers = sorted((o for n, o in objects.items() if n.startswith("Louver_F2_")), key=b)
    assert [o.name for o in sorted(louvers, key=lambda o: o.name)] == [
        f"Louver_F2_{k}" for k in range(1, 7)
    ]
    xs = [b(o)[0][0] for o in louvers]
    gaps = [x2 - x1 for x1, x2 in zip(xs, xs[1:], strict=False)]
    assert max(gaps) - min(gaps) == pytest.approx(0.0, abs=1e-9)
    assert xs[0] == pytest.approx(0.5, abs=TOL) and b(louvers[-1])[1][0] == pytest.approx(1.9)
    for o in louvers:
        lo, hi = b(o)
        assert (lo[1], hi[1]) == pytest.approx((4.35, 4.45), abs=TOL)
        assert (lo[2], hi[2]) == pytest.approx((3.6, 6.6), abs=TOL)  # under frame beam
        assert o.material == "MAT_Louver"


def test_canopy(objects):
    lo, hi = b(objects["Canopy"])
    assert (lo[0], hi[0], lo[1], hi[1], lo[2], hi[2]) == pytest.approx(
        (-2.5, 2.5, 3.3, 4.5, 2.9, 3.02), abs=TOL
    )


def test_four_leaf_door(objects):
    frame, glass = objects["Door_D1_Frame"], objects["Door_D1_Glass"]
    assert frame.collection == glass.collection == "Doors"
    assert frame.material == "MAT_Aluminium" and glass.material == "MAT_Glass"
    lo, hi = b(frame)
    assert (lo[0], hi[0], lo[2], hi[2]) == pytest.approx((-1.6, 1.6, 0.0, 2.6), abs=TOL)
    assert len(glass.mesh.faces) == 5 * 6


def test_windows_and_plain_door(objects):
    assert objects["Door_D2"].material == "MAT_Door"
    for wid in ("W1", "W2", "W3", "W4", "W5"):
        assert objects[f"Window_{wid}_Frame"].collection == "Windows"
        assert len(objects[f"Window_{wid}_Glass"].mesh.faces) == 2 * 6
    lo, hi = b(objects["Window_W4_Frame"])
    assert lo[2] == pytest.approx(6.9 + 0.4, abs=TOL) and lo[1] >= 6.5 - TOL


def test_components_do_not_clash(objects):
    posts_x = ((-2.5, -2.2), (2.2, 2.5))
    for name, o in objects.items():
        if name.startswith("Louver_") or name.startswith("Balcony_"):
            lo, hi = b(o)
            for a, c in posts_x:
                assert hi[0] <= a + TOL or lo[0] >= c - TOL, name
    beam_bottom = 6.9 - 0.3
    for name, o in objects.items():
        if name.startswith("Louver_"):
            assert b(o)[1][2] <= beam_bottom + TOL


def test_everything_inside_lot(objects):
    for name, o in objects.items():
        lo, hi = b(o)
        assert lo[1] >= -TOL and lo[0] >= -2.5 - TOL and hi[0] <= 2.5 + TOL, name
