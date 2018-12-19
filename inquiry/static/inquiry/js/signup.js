// sets all the password input fields and helper text variables
var passwordInput = $("#id_signup-password1");
var confirmPasswordInput = $("#id_signup-password2");
var instructionText = $("#password-instructions");
var lowercaseText = $("#password-lowercase");
var numberText = $("#password-number");
var countText = $("#password-count");
var matchText = $("#password-match");


passwordInput.focus(function() {
  instructionText.slideDown();
  validatePassword();
});

passwordInput.focusout(function() {
  instructionText.slideUp();
});

passwordInput.on('keyup', function() {
    validatePassword();
});

function validatePassword() {
  // checks to make sure the password contains: a lower case letter, a number, and more than 8 characters
  var value = passwordInput.val();

  if (!value.match(/^(?=.*[a-z])/)) { // if lower case letter exists
    markIncomplete(lowercaseText);
  } else {
    markComplete(lowercaseText);
  }
  if (!value.match(/^(?=.*[0-9])/)) { // if number character exists
      markIncomplete(numberText);
  } else {
    markComplete(numberText);
  }
  if (value.length < 8 || value.length > 25) { // if string length less than 8 or greater than 25
      markIncomplete(countText);
  } else {
    markComplete(countText);
  }
}

confirmPasswordInput.focus(function() {
  matchText.slideDown();
  confirmPasswordMatch();

});

confirmPasswordInput.focusout(function() {
  matchText.slideUp();
});

confirmPasswordInput.on('keyup', function() {
  confirmPasswordMatch();
});

function confirmPasswordMatch() {
  var value = confirmPasswordInput.val();
  var checkVal = passwordInput.val();

  if (value !== checkVal || checkVal === '') {
    markIncomplete(matchText);
    matchText.text('✘ Passwords must match.');
  } else {
    matchText.text('✔ Passwords are the same!');
    markComplete(matchText);
  }
}

function markComplete(obj) {
  obj.css("color", "green");
  obj.children('span').text('✔ ');
  // obj.css("text-decoration", "line-through");
}

function markIncomplete(obj) {
  obj.css("color", "red");
  obj.children('span').text('✘ ');
  // obj.css("text-decoration", "none");
}