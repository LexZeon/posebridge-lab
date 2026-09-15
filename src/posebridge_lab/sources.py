"""Enumerate system video sources without pretending Bluetooth means video."""
from urllib.parse import urlsplit


def enumerate_sources(backend):
    import cv2
    from cv2_enumerate_cameras import enumerate_cameras
    api=cv2.CAP_DSHOW if backend=='DSHOW' else cv2.CAP_MSMF
    return [{'index':int(c.index),'name':c.name,'backend':backend} for c in enumerate_cameras(api)]


def validate_network_source(url):
    parts=urlsplit(url)
    if parts.scheme not in ('rtsp','http','https') or not parts.hostname or len(url)>2048:
        raise ValueError('Use an RTSP/HTTP/HTTPS camera stream URL.')
    return url
