import subprocess

subprocess.call(['rm', '-r', 'dist/'])
subprocess.call(['python', '-m', 'pip', 'install', 'build', 'twine'])
subprocess.call(['python', '-m', 'build'])
subprocess.call(['twine', 'check', 'dist/*'])
subprocess.call(['twine', 'upload', 'dist/*'])
subprocess.call(['rm', '-r', 'dist/'])
