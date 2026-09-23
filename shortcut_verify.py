import struct, subprocess, time, sys, os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
# 1) validate ICO structure
data = open("assets/icon.ico", "rb").read()
res, typ, count = struct.unpack("<HHH", data[:6])
print("ICO: type=%d images=%d" % (typ, count))
off = 6
for i in range(count):
    w, h, cc, r, planes, bpp, size, offset = struct.unpack("<BBBBHHII", data[off:off + 16])
    hdr = struct.unpack("<IiiHHII", data[offset:offset + 24])
    print("  entry %d: %dx%d bpp=%d bytes=%d (bmp w=%d h=%d ok=%s)" % (
        i, w or 256, h or 256, bpp, size, hdr[1], hdr[2] // 2,
        hdr[1] == w and hdr[2] // 2 == h))
    off += 16
# 2) launch exactly like the shortcut does (pythonw)
p = subprocess.Popen([r"C:\Users\BANK\AppData\Local\Programs\Python\Python312\pythonw.exe",
                      "run_app.py"])
time.sleep(6)
alive = p.poll() is None
if alive:
    p.terminate()
    try:
        p.wait(timeout=10)
    except subprocess.TimeoutExpired:
        p.kill()
print("PYTHONW LAUNCH:", "RUNNING (OK)" if alive else "EXITED rc=%s" % p.returncode)
