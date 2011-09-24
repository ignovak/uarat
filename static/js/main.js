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
            $('#menu').addClass('user-menu');
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
      $('#menu').removeClass('user-menu');
      console.log('logout');
    });
    return false
  });


});
