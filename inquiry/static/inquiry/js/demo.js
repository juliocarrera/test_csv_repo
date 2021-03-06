// fills out investment inquiry with dummy data

function useDemoData() {
  $("#id_first-street").val("20 University Rd");
  $("#id_first-unit").val("Suite 100");
  $("#id_first-city").val("Cambridge");
  $("#id_first-state").val("MA");
  $("#id_first-zip_code").val("02138");

  checkIfNotChecked("id_first-use_case_debts");
  checkIfNotChecked("id_first-use_case_renovate");

  $("#id_home-property_type").val("sf");
  $("#id_home-rent_type").val("no");
  checkIfNotChecked("id_home-primary_residence_0");
  $("#id_home-ten_year_duration_prediction").val("10_or_less");
  $("#id_home-home_value").val("1000000");
  $("#id_home-household_debt").val(500000);

  $("#id_homeowner-first_name").val("Bob");
  $("#id_homeowner-last_name").val("Smith");
  $("#id_homeowner-referrer_name").val("Sarah Dekin");

  $("#id_homeowner-notes").val("I sure hope I get approved!");
  $("#id_homeowner-when_interested").val("3_to_6_months");

  $("#id_signup-password1").val("testpassword1");
  $("#id_signup-password2").val("testpassword1");
  $("#id_signup-phone_number").val("617-399-0604");

  checkIfNotChecked("id_signup-sms_opt_in");
  checkIfNotChecked("id_signup-agree_to_terms");

  $(".comma-number input").each(function() {
    commifyInput($(this).val(), this)
  });
}
