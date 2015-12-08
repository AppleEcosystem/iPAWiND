const fs = require("fs");
const forge = require("node-forge");
const ocsp = require("ocsp");
//
// who needs an actual arg parser??
// Only use if not null, does not include '--json', and actually exists
const jsonOutput = process.argv.toString().includes("--json");

const p12File = process.argv[2]


if (!fs.existsSync(p12File)) {
	console.log("[!] Certificate must be stored at ./cert.p12, or within a specified directory (via 'node index.js /path/to/dir').");
	process.exit();
} else if (!fs.existsSync("CA-PEM")) {
    console.log("[!] Please run 'resources.js' to retrieve the necessary resources from Apple's servers.\n[*] The downloaded certificates will be automatically converted to the correct format.");
    process.exit();
}
let p12Pass;
if (process.argv[3]) {p12Pass = process.argv[3]} else {p12Pass = ""}

/* Convert P12 to PEM */
let cert, certData;
try {
	const p12 = forge.pkcs12.pkcs12FromAsn1(forge.asn1.fromDer(fs.readFileSync(p12File, {encoding:"binary"})), false, p12Pass);
	certData = p12.getBags({bagType: forge.pki.oids.certBag});
	cert = forge.pki.certificateToPem(certData[forge.pki.oids.certBag][0].cert); // no need to assign to variable, but makes the ocsp.check() line shorter
} catch (err) {
	console.log(`Failed to convert P12 to PEM. ${err.message.includes("Invalid password") ? "Password is likely incorrect" : "Unknown error"}.`);
	process.exit();
}

// Get certificate name
let certName = certData[forge.pki.oids.certBag][0].cert.subject.attributes.filter(({name}) => name === "organizationName")[0].value;
// Get expiration date
let certExpirationDate = new Date(certData[forge.pki.oids.certBag][0].cert.validity.notAfter.getTime()).toGMTString();

/* GET CERT SIGNATURE STATUS */
// Loop througn all CA certificates from CA-PEM folder
// Probably a better way than doing this, but it's fast anyway and doesn't really matter anyway
fs.readdirSync("CA-PEM").forEach(file => {
	// This next line can break if there is a directory ending with .pem, but that's just intentionally breaking the script so idc
	if (file.endsWith(".pem")) { // If PEM file
		// Check if the certificate is signed by the CA
		ocsp.check({cert: cert, issuer: fs.readFileSync(`CA-PEM/${file}`, "utf8")}, function(error, res) {
			let certStatus;
			if (error) {
				if (error.toString().includes("revoked")) certStatus = "Revoked";
			} else if (res.type == "good") certStatus = "Signed";

			if (certStatus) {
				if (jsonOutput) { // If JSON output is requested
					console.log(JSON.stringify({name: certName, status: certStatus, expirationDate: certExpirationDate}));
				} else {
					console.log("Certificate Name: " + certName);
					console.log("Certificate Status: " + certStatus);
					console.log("Certificate Expiration Date: " + certExpirationDate);
				}
				process.exit(); // Exit here so the script doesn't continue to check other certificates
			}
		});
	}
});
