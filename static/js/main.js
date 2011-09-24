$(function() {
  $('.login-btn').click(function() {
    $('#dialog').load('/login', function() {

      $(this).dialog({
        width: 360,
        position: 'center',
        title: 'Sign In'
      });

      $('#login-form').submit(function() {
        var params = {
          email: $('#email').val(),
          password: $('#password').val()
        };
        $.post('/login', params, function(data) {
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
            var params = {};
            $('input[type!=submit]', this).each(function() {
              params[this.name] = this.value;
            });
            $.post('/signup', params, function(data) {
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


});
