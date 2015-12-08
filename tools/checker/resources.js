const fs = require("fs");
const https = require("https");
const execSync = require("child_process").execSync;

const downloadCER = (filename) => {
  const file = fs.createWriteStream(`cctmp-${filename}.cer`);
  // The first CA certificate (AppleWWDRCA) is stored in a different place for some reason...
  const url = filename.endsWith("A") ? "https://developer.apple.com/certificationauthority/AppleWWDRCA.cer" : `https://www.apple.com/certificateauthority/${filename}.cer`;
  https.get(url, (res) => {
    res.pipe(file);
    file.on('finish', () => {
        file.close();
        // Convert CER files to PEM
        console.log(`[*] '${filename}.cer' has been downloaded, converting to PEM format...`);
        execSync(`node ${__dirname}/cer-to-pem.js cctmp-${filename}.cer && mv cctmp-${filename}.pem CA-PEM/${filename}.pem && rm -rf cctmp-${filename}.cer`);
    })
  })
}
console.log('[*] Downloading resources...\n[*] Once complete, you can run the main script again.\n');
if (!fs.existsSync("CA-PEM")) fs.mkdirSync("CA-PEM/");

const certs = ["AppleWWDRCA", "AppleWWDRCAG2", "AppleWWDRCAG3", "AppleWWDRCAG4", "AppleWWDRCAG5", "AppleWWDRCAG6"];
certs.forEach(cert => downloadCER(cert));
