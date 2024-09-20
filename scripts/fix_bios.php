<?php


$host = "127.0.0.1"; //change to prod
$username = "wordpress"; //change to prod
$password = "wordpress"; //change to prod
$database = "wordpress"; //change to prod
$port = 59183; //change to prod


// Create connection
$conn = new mysqli($host, $username, $password, $database, $port);

// Check connection
if ($conn->connect_error) {
    die("Connection failed: " . $conn->connect_error);
}

// get affected bios
$bio_query = "SELECT meta_id, meta_value from wp_postmeta WHERE meta_value REGEXP 'href=\"[“]'";
$result = $conn->query($bio_query);

// process rows
$rows = [];
while($row = $result->fetch_row()) {
    $rows[] = $row;
}

// apply fix
foreach ($rows as $r) {
    $new_bio = preg_replace('/href="[”]{1,}(.+?)[”]{1,}"/', 'href="$1"', $r[1]);
    $result = $conn->query("UPDATE wp_postmeta SET meta_value ='".$conn->real_escape_string($new_bio)."' WHERE meta_id = ".$r[0]);
}

$conn->close();

?>

