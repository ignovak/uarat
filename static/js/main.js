$(function() {
  $('.login-btn').click(function() {
    $('#dialog').load('/login', function() {

      $(this).dialog({
        width: 360,
        position: 'center',
        title: 'Sign In'
      });

      $('#login-form').submit(function() {
        $.post('/login', $(this).serialize(), function(data) {
          if ( data.error ) {
            $('.error', '#dialog').text(data.error);
          } else {
            $('nav').removeClass('guest').addClass(data.role);
            $('strong', '.greeting').text(data.username);
            $('#dialog').dialog('close');
          };
        }, 'json');
        return false;
      });

      $('#signup-btn').click(function() {
        $('#dialog').load('/signup', function() {
          $('#ui-dialog-title-dialog').text('Sign Up')
          $('#signup-form').submit(function() {
            $.post('/signup', $(this).serialize(), function(data) {
              if ( data.error ) {
                $('.error', '#dialog').text(data.error);
              } else {
                console.log('re');
                $('nav').removeClass('guest').addClass('user');
                $('strong', '.greeting').text(data.username);
                $('#dialog').dialog('close');
              };
            }, 'json');
            return false;
          });
        });
        return false
      })
    });

    return false
  });

  $('.logout-btn').click(function() {
    $.get('/logout', function(data) {
      $('nav').removeClass('user admin').addClass('guest');
      $('strong', '.greeting').text('Гость');
    });
    return false
  });

  $('.post-link').click(function() {
    var url = this.href;
    if ( $('#post-form').length ) {
      $('textarea', '#post-form').focus();
    } else {
      $.get(url, function(data) {
        $(data).insertAfter($('.content'));
        $('textarea', '#post-form').focus();

        $('#post-form').submit(function() {
          $.post(url, $(this).serialize(), function(data) {
            console.log(data);
            return
            if ( data.error ) {
              $('.error', '#dialog').text(data.error);
            } else {
              $('nav').removeClass('guest').addClass(data.role);
              $('strong', '.greeting').text(data.username);
              $('#dialog').dialog('close');
            };
          }, 'json');
          return false;
        });

      });
    };
    return false
  })

});
