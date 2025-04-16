try:
    from pyresample.geometry import AreaDefinition, SwathDefinition
    from pyresample.kd_tree import XArrayResamplerNN  # noqa: F401

    has_pyresample = True
except ImportError:
    print("PyResample not installed.  Some functionality will be lost")
    has_pyresample = False
try:
    import xesmf  # noqa: F401

    has_xesmf = True
except ImportError:
    has_xesmf = False


def _ensure_swathdef_compatability(defn):
    """Ensures the SwathDefinition is compatible with XArrayResamplerNN.

    Converts longitude and latitude arrays in the SwathDefinition to xarray
    DataArrays if they aren't already, which is required for XArrayResamplerNN.

    Parameters
    ----------
    defn : pyresample.geometry.SwathDefinition
        A :class:`pyresample.geometry.SwathDefinition` instance.

    Returns
    -------
    pyresample.geometry.SwathDefinition
        A compatible SwathDefinition with xarray DataArrays for lons and lats.
    """
    import xarray as xr

    if isinstance(defn.lons, xr.DataArray):
        return defn  # do nothing
    else:
        defn.lons = xr.DataArray(defn.lons, dims=["y", "x"]).chunk()
        defn.lats = xr.DataArray(defn.lons, dims=["y", "x"]).chunk()
        return defn


def _check_swath_or_area(defn):
    """Checks for a SwathDefinition or AreaDefinition. If AreaDefinition do
    nothing else ensure compatibility with XArrayResamplerNN.

    Parameters
    ----------
    defn : pyresample.geometry.SwathDefinition or pyresample.geometry.AreaDefinition
        The grid definition to check and potentially convert.

    Returns
    -------
    pyresample.geometry.SwathDefinition or pyresample.geometry.AreaDefinition
        The (potentially modified) grid definition ensuring compatibility
        with XArrayResamplerNN.
    """
    try:
        if isinstance(defn, SwathDefinition):
            newswath = _ensure_swathdef_compatability(defn)
        elif isinstance(defn, AreaDefinition):
            newswath = defn
        else:
            raise RuntimeError
    except RuntimeError:
        print("grid definition must be a pyresample SwathDefinition or AreaDefinition")
        return
    return newswath


def _reformat_resampled_data(orig, new, target_grid):
    """Reformats the resampled data array filling in coords, name and attrs.

    After resampling, this function ensures the new DataArray has proper
    coordinates, name, and attributes from the original.

    Parameters
    ----------
    orig : xarray.DataArray
        Original input DataArray.
    new : xarray.DataArray
        Resampled xarray.DataArray
    target_grid : pyresample.geometry
        Target grid is the target SwathDefinition or AreaDefinition

    Returns
    -------
    xarray.DataArray
        Reformatted xarray.DataArray with proper coordinates and attributes.
    """
    target_lon, target_lat = target_grid.get_lonlats_dask()
    new.name = orig.name
    new["latitude"] = (("y", "x"), target_lat)
    new["longitude"] = (("y", "x"), target_lon)
    new.attrs["area"] = target_grid
    return new


def resample_stratify(da, levels, vertical, axis=1):
    """Vertically interpolate data to specified levels.

    Uses stratify package to interpolate a DataArray to new vertical levels.

    Parameters
    ----------
    da : xarray.DataArray
        The data to interpolate. Must have a vertical dimension.
    levels : array-like
        The target vertical levels to interpolate to.
    vertical : array-like
        The current vertical coordinate values.
    axis : int, default 1
        The axis representing the vertical dimension.

    Returns
    -------
    xarray.DataArray
        Data interpolated to the new vertical levels, preserving attributes
        and other coordinates.
    """
    import stratify
    import xarray as xr

    result = stratify.interpolate(levels, vertical.chunk().data, da.chunk().data, axis=axis)
    dims = da.dims
    out = xr.DataArray(result, dims=dims, name=da.name)
    out.attrs = da.attrs.copy()
    if len(da.coords) > 0:
        for vn in da.coords:
            if vn != "z" and "z" not in da[vn].dims:
                out[vn] = da[vn].copy()
    return out


def resample_xesmf(source_da, target_da, cleanup=False, **kwargs):
    """Resample data from one grid to another using xESMF.

    Uses xESMF to perform regridding between different coordinate systems and grids.

    Parameters
    ----------
    source_da : xarray.DataArray or xarray.Dataset
        The source data to regrid.
    target_da : xarray.DataArray or xarray.Dataset
        The target grid to regrid onto.
    cleanup : bool, default False
        Whether to remove the temporary weight file after regridding.
    **kwargs
        Additional keyword arguments passed to xesmf.Regridder constructor.
        Common options include 'method' and 'locstream_out'.

    Returns
    -------
    xarray.DataArray or xarray.Dataset
        The regridded data with the same type as source_da.
    """
    if has_xesmf:
        import xarray as xr
        import xesmf as xe

        regridder = xe.Regridder(source_da, target_da, **kwargs)
        if cleanup:
            regridder.clean_weight_file()
        if isinstance(source_da, xr.Dataset):
            das = {}
            for name, i in source_da.data_vars.items():
                das[name] = regridder(i)
            ds = xr.Dataset(das)
            ds.attrs = source_da.attrs
            return ds
        else:
            da = regridder(source_da)
            if da.name is None:
                da.name = source_da.name
            return da
