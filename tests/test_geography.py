from earth_pulse.geography import (
    country_name,
    identify_country,
    point_in_feature,
    sample_country_points,
)


def test_identifies_india_from_the_bundled_country_boundary():
    feature = identify_country(21.1458, 79.0882)

    assert feature is not None
    assert country_name(feature) == "India"


def test_ocean_coordinate_has_no_country():
    assert identify_country(0.0, -140.0) is None


def test_country_polygon_crossing_the_antimeridian_is_detected():
    feature = identify_country(-16.2, -179.9)

    assert feature is not None
    assert country_name(feature) == "Fiji"


def test_polygon_holes_are_not_reported_as_country_land():
    feature = {
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [[0, 0], [4, 0], [4, 4], [0, 4], [0, 0]],
                [[1, 1], [3, 1], [3, 3], [1, 3], [1, 1]],
            ],
        }
    }

    assert point_in_feature(0.5, 0.5, feature)
    assert not point_in_feature(2.0, 2.0, feature)


def test_country_samples_are_inside_and_spatially_distinct():
    feature = identify_country(21.1458, 79.0882)
    assert feature is not None

    points = sample_country_points(feature, anchor=(21.1458, 79.0882), max_points=5)

    assert len(points) == 5
    assert all(point_in_feature(latitude, longitude, feature) for latitude, longitude in points)
    assert len(set(points)) == len(points)