<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
<title>MICC Pipeline Subject Identifier</title>
<link rel="stylesheet" type="text/css" href="view.css" media="all">

</head>
<?php
$AccessionNumber = preg_replace("/[^A-Za-z0-9]/", '', $_POST["element_1"]);
$Subject = preg_replace("/[^A-Za-z0-9]/", '', $_POST["element_2"]);
$Session = preg_replace("/[^A-Za-z0-9]/", '', $_POST["element_3"]);
$error = $Subject == "" or $AccessionNumber == "";
if (! $error) {
	$fp = fopen("/data/pipeline/registry/accession.csv", "a");
	fputcsv($fp, array($AccessionNumber, $Subject, $Session));
}
?>
  <body id="main_body" >
	<div id="form_container">
		<h1><a>MICC Pipeline</a></h1>
		<form  class="appnitro"  >
					<div class="form_description">
			<h2><?php if ($error) {
	print("Error...");
} else {
	print("Thank you.");
}?></h2>
            <p><?php
if ($error) {
	print("<p><font color='#a00'>The AccessionNumber and Subject cannot be blank.
                <p>Please go back and try again.</font></p>");
} else {
	print("<p>The pipeline should continue shortly.</p>");
} ?>
		</div>
            <?php
print("<p><font color='#999'>You entered:<br>");
print("AccessionNumber: $AccessionNumber<br>");
print("Subject: $Subject<br>");
print("Session: $Session</font></p>");
?>
		</form>
        </div>
	</body>
</html>
