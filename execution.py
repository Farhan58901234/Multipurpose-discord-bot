import subprocess

# make ffmpeg and ffprobe executable
subprocess.run(["chmod", "+x", "./ffmpeg", "./ffprobe"], check=True)

# check ffmpeg version
result = subprocess.run(["./ffmpeg", "-version"], capture_output=True, text=True)

print(result.stdout)
