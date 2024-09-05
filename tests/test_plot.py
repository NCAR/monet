import cartopy
import cartopy.crs as ccrs
import matplotlib.pyplot as plt
import pytest
import xarray as xr
from packaging.version import Version

import monet  # noqa: F401
from monet.plots.mapgen import draw_map

cartopy_version = Version(cartopy.__version__)

da = xr.tutorial.load_dataset("air_temperature").air.isel(time=1)


@pytest.mark.parametrize("which", ["imshow", "map", "contourf"])
def test_quick(which):
    getattr(da.monet, f"quick_{which}")()


@pytest.mark.parametrize("which", ["imshow", "map", "contourf"])
def test_quick_with_ax(which):
    _, ax = plt.subplots()

    with pytest.raises(TypeError, match="`ax` should be a Cartopy GeoAxes instance"):
        getattr(da.monet, f"quick_{which}")(ax=ax)


@pytest.mark.parametrize("which", ["imshow", "map", "contourf"])
def test_quick_with_cartopy_ax(which):
    proj = tran = ccrs.PlateCarree()

    _, ax = plt.subplots(subplot_kw=dict(projection=proj))

    getattr(da.monet, f"quick_{which}")(ax=ax, transform=tran)


def test_draw_map_counties():
    _ = draw_map(counties=True, extent=[-110.5, -101, 36, 42])


if __name__ == "__main__":
    test_quick("map")
    test_draw_map_counties()

    plt.show()
