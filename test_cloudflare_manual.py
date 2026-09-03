import time
from backend.tunnel import CloudflareTunnel

def on_url(url):
    print("URL FOUND:", url)

def on_status(status):
    print("STATUS:", status)

cf = CloudflareTunnel(5055)
cf.start(on_url, on_status)
time.sleep(15)
cf.stop()
