"""Small reproducible real-data probe; no web application dependencies."""
import hashlib
import json
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / 'data' / 'mpl'))
import numpy as np
from eccodes import codes_grib_new_from_file, codes_get, codes_get_array, codes_release
from ecmwf.opendata import Client


def to_mm(values, units):
    if units == 'm':
        return values * 1000
    if units in ('kg m**-2', 'kg m-2', 'mm'):
        return values.copy()
    raise ValueError(f'Unsupported precipitation units: {units}')


def interval(previous, current, tolerance):
    delta = current - previous
    if np.min(delta) < -tolerance:
        raise ValueError('Accumulation decreased beyond GRIB packing tolerance')
    return np.maximum(delta, 0)


def main():
    (ROOT / 'data').mkdir(exist_ok=True)
    (ROOT / 'reports').mkdir(exist_ok=True)
    client = Client(source='ecmwf', model='ifs', resol='0p25', maximum_retries=2, retry_after=2, use_server_retry_after=False)
    started = time.monotonic()
    run = client.latest(type='fc', stream='oper', step=12, param='tp')
    target = ROOT / 'data' / f'ifs-{run:%Y%m%d%H}-tp.grib2'
    if not target.exists():
        client.retrieve(date=run.strftime('%Y%m%d'), time=run.hour, stream='oper',
                        type='fc', step=[3, 6, 9, 12], param='tp', target=str(target))
    fetch_seconds = time.monotonic() - started
    fields = []
    with target.open('rb') as f:
        while (gid := codes_grib_new_from_file(f)) is not None:
            try:
                keys = ['shortName', 'paramId', 'units', 'stepType', 'startStep', 'endStep',
                        'dataDate', 'dataTime', 'validityDate', 'validityTime', 'Ni', 'Nj',
                        'gridType', 'numberOfMissing', 'packingError']
                meta = {key: codes_get(gid, key) for key in keys}
                values = to_mm(codes_get_array(gid, 'values'), meta['units'])
                lat = codes_get_array(gid, 'latitudes')
                lon = (codes_get_array(gid, 'longitudes') + 180) % 360 - 180
                assert meta['shortName'] == 'tp' and meta['stepType'] == 'accum'
                assert meta['startStep'] == 0 and meta['numberOfMissing'] == 0
                assert np.all(np.isfinite(values))
                meta['global_min_mm'] = float(values.min())
                meta['global_max_mm'] = float(values.max())
                fields.append((meta, values))
            finally:
                codes_release(gid)
    fields.sort(key=lambda item: item[0]['endStep'])
    assert [x[0]['endStep'] for x in fields] == [3, 6, 9, 12]
    assert len({(x[0]['dataDate'], x[0]['dataTime'], x[0]['Ni'], x[0]['Nj']) for x in fields}) == 1
    cities = {'Mumbai': (19.076, 72.878), 'Pune': (18.520, 73.857),
              'Chennai': (13.083, 80.271), 'Delhi': (28.614, 77.209)}
    region = (lat >= 5) & (lat <= 38) & (lon >= 65) & (lon <= 100)
    wet_index = int(np.argmax(np.where(region, fields[-1][1], -np.inf)))
    cities['Wettest regional grid'] = (float(lat[wet_index]), float(lon[wet_index]))
    samples = []
    intervals = []
    previous = np.zeros_like(fields[0][1])
    previous_error = 0.0
    for meta, values in fields:
        error = float(to_mm(np.array([meta['packingError']]), meta['units'])[0])
        delta = interval(previous, values, error + previous_error + 1e-8)
        intervals.append(delta)
        row = {'start_hour': meta['endStep'] - 3, 'end_hour': meta['endStep'], 'cities': {}}
        for name, (y, x) in cities.items():
            index = int(np.argmin((lat-y)**2 + ((lon-x)*np.cos(np.deg2rad(y)))**2))
            row['cities'][name] = {'grid_lat': float(lat[index]), 'grid_lon': float(lon[index]),
                                    'interval_mm': float(delta[index]), 'cumulative_mm': float(values[index])}
        row['minimum_raw_difference_mm'] = float((values-previous).min())
        row['packing_tolerance_mm'] = error + previous_error + 1e-8
        row['negative_differences_clipped'] = int(np.count_nonzero(values-previous < 0))
        samples.append(row)
        previous, previous_error = values, error
    report = {'source': 'ECMWF Open Data primary server', 'model': 'ifs', 'run_utc': run.isoformat(),
              'file': target.name, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
              'download_bytes': target.stat().st_size, 'discovery_and_fetch_seconds': fetch_seconds,
              'fields': [x[0] for x in fields], 'intervals': samples,
              'note': 'Forecast values, not observations. City values use nearest grid point. Times UTC.'}
    (ROOT / 'reports' / 'sample.json').write_text(json.dumps(report, indent=2) + '\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    region = (lat >= 5) & (lat <= 38) & (lon >= 65) & (lon <= 100)
    ys = np.unique(lat[region])[::-1]
    xs = np.unique(lon[region])
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), constrained_layout=True)
    order = np.lexsort((lon[region], -lat[region]))
    grid = intervals[-1][region][order].reshape(len(ys), len(xs))
    mesh = axes[0].pcolormesh(xs, ys, grid, shading='nearest', cmap='Blues', vmin=0)
    fig.colorbar(mesh, ax=axes[0], label='Precipitation (mm / 3 hours)')
    axes[0].set(title='India-region grid: forecast hours 9–12', xlabel='Longitude', ylabel='Latitude')
    for name, (y, x) in cities.items():
        axes[0].plot(x, y, 'k.', markersize=3)
        axes[0].text(x+.3, y, name, fontsize=7)
        axes[1].plot([3,6,9,12], [r['cities'][name]['interval_mm'] for r in samples], marker='o', label=name)
    axes[1].set(title='Nearest-grid-point interval amounts', xlabel='Forecast interval end (hours)', ylabel='Precipitation (mm / 3 hours)', xticks=[3,6,9,12])
    axes[1].set_ylim(bottom=0)
    axes[1].legend(fontsize=8)
    fig.suptitle(f'IFS {run:%Y-%m-%d %H:%M} UTC · ECMWF Open Data · exploratory forecast sample')
    fig.savefig(ROOT / 'reports' / 'exploration.png', dpi=150)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
