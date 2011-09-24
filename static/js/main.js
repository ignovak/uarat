$(function() {
  $('.login-btn').click(function() {
    $('#dialog').load('/login', function() {
      $(this).dialog({
        width: 360,
        position: 'center',
        title: 'sign in'
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
            $('nav').removeClass('guest').addClass('user');
            $('#dialog').dialog('close');
          };
        }, 'json');
        return false;
      });
    });

    return false
  });

  $('.logout-btn').click(function() {
    $.get('/logout', function(data) {
      $('nav').removeClass('user').addClass('guest');
    });
    return false
  });


});
