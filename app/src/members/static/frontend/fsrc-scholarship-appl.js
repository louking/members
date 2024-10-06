      $('#form').submit(function (e) {
          e.preventDefault();
          var file;
          var fileCounter = 0;
          var fd = new FormData();
          var files = $('#files')[0].files;

          if (files.length === 0) {
            showError("Please select a file to upload");
            return;
          }

          var totalsize = 0;

          for (i=0; i<files.length; i++) {
            file = files[i];

            if (file.size > 9 * 1024 * 1024) {
              showError("Each file must be less than 9 MB. " + file.name + " exceeds limit");
              return;
            }

            totalsize += file.size;
            if (totalsize > 24 * 1024 * 1024) {
              showError("All files together must be less than 24 MB");
              return;
            }

          };

          // append all the files, and other form parameters
          for (i=0; i<files.length; i++) {
              file = files[i];
              fd.append('file['+i+']', file);
          }
          fd.append('numfiles', files.length);
          fd.append('email', $('#email').val());
          fd.append('name', $('#name').val());

          showMessage('Uploading files. Please wait...')
          $.ajax({
              url: window.location.href,
              data: fd,
              processData: false,
              contentType: false,
              type: 'POST',
              success: showSuccess
          });
      });

      function showSuccess(e) {
        if (e.status === "OK") {
          $('#forminner').hide();
          $('#success').show();
        } else {
          showError(e.error);
        }
      }

      $('#morefiles').click(function(e){
          e.preventDefault()
          $('#success').hide();
          $('#forminner').show();
          showMessage('')
          $('#files').val('');
          $('.file-path').val('');
      });

      function showError(e) {
        $('#progress').addClass('red-text').html(e);
      }

      function showMessage(e) {
        $('#progress').removeClass('red-text').html(e);
      }


