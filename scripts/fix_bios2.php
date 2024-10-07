<?php

$host = "database.internal"; //change to prod
$username = "user"; //change to prod
$password = ""; //change to prod
$database = "main"; //change to prod
$port = 3306; //change to prod


// Create connection
$conn = new mysqli($host, $username, $password, $database, $port);

// Check connection
if ($conn->connect_error) {
    die("Connection failed: " . $conn->connect_error);
}

error_log($conn);

$conn->close();

?>

