"""Record pace from the 2022 FKT tracker pings (kit/fkt_splits.json): km <-> elapsed hours.
Falls back to an even spread of record_h over the route if the file is missing."""
import bisect, json, os
_P = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fkt_splits.json")
_KH = json.load(open(_P))["km_h"] if os.path.isfile(_P) else None
def _interp(xs, ys, x):
    if x <= xs[0]: return ys[0]
    if x >= xs[-1]: return ys[-1]
    i = bisect.bisect_right(xs, x); x0, x1, y0, y1 = xs[i-1], xs[i], ys[i-1], ys[i]
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
def record_h_at(km, route_km, record_h):
    """hours the record holder needed to reach km"""
    if not _KH: return km / route_km * record_h
    return _interp([k for k, _ in _KH], [h for _, h in _KH], km)
def record_km_at(h, route_km, record_h):
    """where the record holder was after h hours (the FKT dot)"""
    if not _KH: return max(0, min(route_km, h / record_h * route_km))
    return _interp([h_ for _, h_ in _KH], [k for k, _ in _KH], h)
