#!/usr/bin/env python

"""
Python script for building documentation.

To build the docs you must have all optional dependencies for statsmodels
installed. See the installation instructions for a list of these.

Note: currently latex builds do not work because of table formats that are not
supported in the latex generation.

Usage
-----
python make.py clean
python make.py html
"""

import glob
import os
import shutil
import sys
import sphinx

os.environ['PYTHONPATH'] = '..'

SPHINX_BUILD = 'sphinxbuild'

def upload_dev():
    'push a copy to the pydata dev directory'
    if os.system('cd build/html; rsync -avz . pandas@pandas.pydata.org'
                 ':/usr/share/nginx/pandas/pandas-docs/dev/ -essh'):
        raise SystemExit('Upload to Pydata Dev failed')

def upload_dev_pdf():
    'push a copy to the pydata dev directory'
    if os.system('cd build/latex; scp pandas.pdf pandas@pandas.pydata.org'
                 ':/usr/share/nginx/pandas/pandas-docs/dev/'):
        raise SystemExit('PDF upload to Pydata Dev failed')

def upload_stable():
    'push a copy to the pydata stable directory'
    if os.system('cd build/html; rsync -avz . pandas@pandas.pydata.org'
                 ':/usr/share/nginx/pandas/pandas-docs/stable/ -essh'):
        raise SystemExit('Upload to stable failed')

def upload_stable_pdf():
    'push a copy to the pydata dev directory'
    if os.system('cd build/latex; scp pandas.pdf pandas@pandas.pydata.org'
                 ':/usr/share/nginx/pandas/pandas-docs/stable/'):
        raise SystemExit('PDF upload to stable failed')

def clean():
    if os.path.exists('build'):
        shutil.rmtree('build')

    if os.path.exists('source/generated'):
        shutil.rmtree('source/generated')

def html():
    check_build()
    if os.system('sphinx-build -P -b html -d build/doctrees '
                 'source build/html'):
        raise SystemExit("Building HTML failed.")

def latex():
    check_build()
    if sys.platform != 'win32':
        # LaTeX format.
        if os.system('sphinx-build -b latex -d build/doctrees '
                     'source build/latex'):
            raise SystemExit("Building LaTeX failed.")
        # Produce pdf.

        os.chdir('build/latex')

        # Call the makefile produced by sphinx...
        if os.system('make'):
            raise SystemExit("Rendering LaTeX failed.")

        os.chdir('../..')
    else:
        print 'latex build has not been tested on windows'

def check_build():
    build_dirs = [
        'build', 'build/doctrees', 'build/html',
        'build/latex', 'build/plots', 'build/_static',
        'build/_templates']
    for d in build_dirs:
        try:
            os.mkdir(d)
        except OSError:
            pass

def all():
    # clean()
    html()

def auto_dev_build():
    msg = ''
    try:
        clean()
        html()
        latex()
        upload_dev()
        upload_dev_pdf()
        sendmail()
    except (Exception, SystemExit), inst:
        msg += str(inst) + '\n'
        sendmail(msg)

def sendmail(err_msg=None):
    from_name, to_name = _get_config()

    if err_msg is None:
        msgstr = 'Daily docs build completed successfully'
        subject = "DOC: daily build successful"
    else:
        msgstr = err_msg
        subject = "DOC: daily build failed"

    import smtplib
    from email.MIMEText import MIMEText
    msg = MIMEText(msgstr)
    msg['Subject'] = subject
    msg['From'] = from_name
    msg['To'] = to_name

    server_str, port, login, pwd = _get_credentials()
    server = smtplib.SMTP(server_str, port)
    server.ehlo()
    server.starttls()
    server.ehlo()

    server.login(login, pwd)
    try:
        server.sendmail(from_name, to_name, msg.as_string())
    finally:
        server.close()

def _get_dir():
    import getpass
    USERNAME = getpass.getuser()
    if sys.platform == 'darwin':
        HOME = '/Users/%s' % USERNAME
    else:
        HOME = '/home/%s' % USERNAME

    tmp_dir = '%s/tmp' % HOME
    return tmp_dir

def _get_credentials():
    tmp_dir = _get_dir()
    cred = '%s/credentials' % tmp_dir
    with open(cred, 'r') as fh:
        server, port, un, domain = fh.read().split(',')
    port = int(port)
    login = un + '@' + domain + '.com'

    import base64
    with open('%s/cron_email_pwd' % tmp_dir, 'r') as fh:
        pwd = base64.b64decode(fh.read())

    return server, port, login, pwd

def _get_config():
    tmp_dir = _get_dir()
    with open('%s/config' % tmp_dir, 'r') as fh:
        from_name, to_name = fh.read().split(',')
    return from_name, to_name

funcd = {
    'html'     : html,
    'upload_dev' : upload_dev,
    'upload_stable' : upload_stable,
    'upload_dev_pdf' : upload_dev_pdf,
    'upload_stable_pdf' : upload_stable_pdf,
    'latex'    : latex,
    'clean'    : clean,
    'auto_dev' : auto_dev_build,
    'all'      : all,
    }

small_docs = False

# current_dir = os.getcwd()
# os.chdir(os.path.dirname(os.path.join(current_dir, __file__)))

if len(sys.argv)>1:
    for arg in sys.argv[1:]:
        func = funcd.get(arg)
        if func is None:
            raise SystemExit('Do not know how to handle %s; valid args are %s'%(
                    arg, funcd.keys()))
        func()
else:
    small_docs = False
    all()
#os.chdir(current_dir)
