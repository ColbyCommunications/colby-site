const { execSync } = require("child_process");
const path = require("path");

const signatureDirectory = path.join(__dirname, "signature");

try {
  // Change directory to the Signature directory
  process.chdir(signatureDirectory);

  // Execute the npm run build command
  execSync("npm run build", { stdio: "inherit" });
} catch (error) {
  console.error("Error occurred during the build:", error);
  process.exit(1);
}
