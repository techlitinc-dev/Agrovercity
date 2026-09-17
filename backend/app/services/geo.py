from typing import Protocol


class GeoAdapter(Protocol):
    def reverse(self, lat: float, lng: float) -> dict: ...


class MockGeoAdapter:
    _BOXES = [
        (
            (19.9, 20.2, 73.6, 74.1),
            {"state": "Maharashtra", "district": "Nashik", "region": "West", "suggestedLanguages": ["mr", "hi"]},
        ),
        (
            (30.8, 31.1, 75.7, 76.1),
            {"state": "Punjab", "district": "Ludhiana", "region": "North", "suggestedLanguages": ["pa", "hi"]},
        ),
    ]
    _FALLBACK = {"state": "Maharashtra", "district": "Unknown", "region": "West", "suggestedLanguages": ["hi", "en"]}

    def reverse(self, lat: float, lng: float) -> dict:
        for (min_lat, max_lat, min_lng, max_lng), result in self._BOXES:
            if min_lat <= lat <= max_lat and min_lng <= lng <= max_lng:
                return result
        return self._FALLBACK


adapter: GeoAdapter = MockGeoAdapter()
