const fs = require("fs");

const filepath = process.argv[2];
if (!filepath) {
    console.log("Incorrect usage. Usage: node cer-to-pem.js <path to .cer file>");
    process.exit();
} else if (!fs.existsSync(filepath)) {
    console.log(`File '${filepath}' does not exist`);
    process.exit();
}

const cert = fs.readFileSync(filepath);
const certB64 = Buffer.from(cert).toString("base64");
/*
    Split the certificate into lines of upto 64 characters
    
    https://www.rfc-editor.org/rfc/rfc7468 states:
        Generators MUST wrap the base64-encoded lines so that each line
        consists of exactly 64 characters except for the final line, which
        will encode the remainder of the data

*/
const lines = certB64.match(/.{1,64}/g);

// Start to build the PEM file
let output = "-----BEGIN CERTIFICATE-----\n";
// Add each line of the certificate
lines.forEach(line => output += line + "\n");
// Add the ending line of the certificate
output += "-----END CERTIFICATE-----\n";
// Write the PEM file to the same directory as the .cer file
fs.writeFileSync(filepath.replace(".cer", ".pem"), output);
console.log(`Converted ${filepath} to ${filepath.replace(".cer", ".pem")}`);
