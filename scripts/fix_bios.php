<?php

// Define the query to select affected bios
$bio_query = "SELECT meta_id, meta_value FROM wp_postmeta WHERE meta_value REGEXP 'href=\"[“]'";

// Execute the query using the MySQL command line
$output = shell_exec("mysql -h database.internal -P 3306 -u user main -e \"$bio_query\"");

// Check if there are results
if ($output) {
    // Split the output into rows
    $rows = explode("\n", trim($output));
    array_shift($rows); // Remove the header row

    // Process each row
    foreach ($rows as $row) {
        $fields = explode("\t", $row);
        $meta_id = $fields[0];
        $meta_value = $fields[1];

        // Apply the fix to the bio
        $new_bio = preg_replace('/href="[”]{1,}(.+?)[”]{1,}"/', 'href="$1"', $meta_value);

        echo $new_bio;
        // Update the row using MySQL command line
        // $update_query = "UPDATE wp_postmeta SET meta_value = '".addslashes($new_bio)."' WHERE meta_id = $meta_id";
        // shell_exec("mysql -h database.internal -P 3306 -u user main -e \"$update_query\"");
    }
} else {
    echo "No rows matched the query.";
}

?>
