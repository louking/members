'''
fsrc_views - views specific to the Frederick Steeplechasers Running Club
===========================================================================
'''

# standard
from tempfile import TemporaryDirectory
from os.path import join as pathjoin
from mimetypes import guess_type
from shutil import rmtree

# pypi
from flask import request, render_template, jsonify, current_app
from flask.views import MethodView
from werkzeug.utils import secure_filename
from googleapiclient.http import MediaFileUpload

# homegrown
from . import bp
from loutilities.googleauth import GoogleAuthService
from loutilities.flask_helpers.mailer import sendmail

def allowed_file(filename):
    return True

# todo: move this into GoogleAuthService
class FsrcGoogleAuthService(GoogleAuthService):
    def create_file(self, folderid, filename, contents, doctype='html'):
        """
        create file in drive folder

        ..note::
            folderid must be shared read/write with services account email address

        :param folderid: drive id for folder file needs to reside in
        :param filename: name for file on drive
        :param contents: path for file contents
        :param doctype: 'html' or 'docx', default 'html'
        :return: google drive id for created file
        """
        # mimetype depends on doctype
        mimetype = guess_type(filename)[0]

        ## upload (adapted from https://developers.google.com/drive/api/v3/manage-uploads)
        file_metadata = {
            'name': filename,
            # see https://developers.google.com/drive/api/v3/mime-types
            'mimeType': mimetype,
            # see https://developers.google.com/drive/api/v3/folder
            'parents': [folderid],
        }

        # create file
        media = MediaFileUpload(
            contents,
            mimetype=mimetype,
            resumable=True
        )
        file = self.drive.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        fileid = file.get('id')
        return fileid

    def create_folder(self, parentid, foldername):
        file_metadata = {
            'name': foldername,
            # see https://developers.google.com/drive/api/v3/mime-types
            'mimeType': 'application/vnd.google-apps.folder',
            # see https://developers.google.com/drive/api/v3/folder
            'parents': [parentid],
        }

        file = self.drive.files().create(
            body=file_metadata,
            fields='id'
        ).execute()
        fileid = file.get('id')
        return fileid

    def list_files(self, folderid, filename=None):
        retfiles = []
        page_token = None
        while True:
            # https://developers.google.com/drive/api/v3/search-files
            q = '\'{}\' in parents'.format(folderid)
            if filename:
                q += ' and name = \'{}\''.format(filename)
            response = self.drive.files().list(
                q=q,
                spaces='drive',
                fields='nextPageToken, files(id, name)',
                pageToken=page_token
            ).execute()
            for file in response.get('files', []):
                retfiles.append({file.get('name'): file.get('id')})
            page_token = response.get('nextPageToken', None)
            if not page_token:
                break

        return retfiles

class FsrcMemScholarshipAppl(MethodView):

    def get(self):
        return render_template('fsrc-scholarship-appl.jinja2')

    def post(self):
        # see https://flask.palletsprojects.com/en/1.1.x/patterns/fileuploads/
        # check if the post request has the file part
        try:
            if 'file[0]' not in request.files:
                return jsonify({'status': 'error', 'error': 'No files submitted'})
            gs = FsrcGoogleAuthService(current_app.config['GSUITE_SERVICE_KEY_FILE'], current_app.config['GSUITE_SCOPES'])
            parentid = current_app.config['FSRC_SCHOLARSHIP_FOLDER']

            tmpdir = TemporaryDirectory(prefix='mbr-frsc-')
            for i in range(int(request.form['numfiles'])):
                file = request.files['file[{}]'.format(i)]
                # if user does not select file, browser also
                # submit an empty part without filename
                if file.filename == '':
                    return jsonify({'status': 'error', 'error': 'Empty filename detected for file {}'.format(i)})
                name = request.form.get('name', '')
                if not name:
                    return jsonify({'status': 'error', 'error': 'Name must be supplied'})
                email = request.form.get('email', '')
                if not email:
                    return jsonify({'status': 'error', 'error': 'Email must be supplied'})
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    applnfoldername = '{} {}'.format(name, email)

                    # has applicant already submitted? reuse filedid if so
                    # should not be more than one of these, but use the first one if any found
                    applnfolders = gs.list_files(parentid, filename=applnfoldername)
                    if applnfolders:
                        folderid = applnfolders[0][applnfoldername]
                    else:
                        folderid = gs.create_folder(parentid, applnfoldername)

                    current_app.logger.info('fsrcmemscholarshipappl: {}/{} processing '
                                            'file {}'.format(name, email, filename))
                    docpath = pathjoin(tmpdir.name, filename)
                    file.save(docpath)
                    fileid = gs.create_file(folderid, filename, docpath, doctype=None)

            # remove temporary directory
            rmtree(tmpdir.name, ignore_errors=True)

            # send mail to administrator
            foldermeta = gs.drive.files().get(fileId=folderid, fields='webViewLink').execute()
            folderlink = foldermeta['webViewLink']
            subject = "[FSRC Memorial Scholarship] Application from {}".format(name)
            from dominate.tags import div, p, a
            from dominate.util import text
            body = div()
            with body:
                p('Application received from {} {}'.format(name, email))
                with p():
                    text('See ')
                    a(folderlink, href=folderlink)
            html = body.render()
            tolist = current_app.config['FSRC_SCHOLARSHIP_EMAIL']
            fromlist = current_app.config['FSRC_SCHOLARSHIP_EMAIL']
            cclist = None
            sendmail(subject, fromlist, tolist, html, ccaddr=cclist)

            return jsonify({'status': 'OK'})

        except Exception as e:
            from traceback import format_exc
            from html import escape
            error = format_exc()
            return jsonify({'status': 'error', 'error': escape(repr(e))})

bp.add_url_rule('/fsrcmemscholarshipappl', view_func=FsrcMemScholarshipAppl.as_view('fsrcmemscholarshipappl'),
                methods=['GET', 'POST'])
