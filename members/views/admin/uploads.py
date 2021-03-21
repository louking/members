"""
uploads - support upload and download of files, e.g., for ckeditor images
"""

# standard

# pypi
from flask import request, jsonify, url_for, send_file
from flask.views import MethodView
from flask_uploads import UploadSet, configure_uploads, IMAGES

# homegrown
from . import bp

images = UploadSet('images', IMAGES)

def init_uploads(app):
    configure_uploads(app, (images,))

# upload files
class UploadView(MethodView):
    def post(self):
        filename = images.save(request.files['upload'])

        # see https://ckeditor.com/docs/ckeditor5/latest/features/image-upload/simple-upload-adapter.html#successful-upload
        return jsonify({
            'url': url_for('_uploads.uploaded_file', setname='images', filename=filename, _external=True)
        })
bp.add_url_rule('/uploads', view_func=UploadView.as_view('uploads'), methods=['POST'])


