api_id = 8  # get this from my.telegram.org
api_hash = "7245de8e747a0d6fbe11f7cc14fcc0bb" # get this from my.telegram.org
bot_token = "Your Bot Token"  # get it from @botfather
server_address = "https://signipa.org/api"

PASSWORD = "1"
api_key = ""
api_urls = []

admin = [719363292]
reseller = []

web_path = "/var/www/html"
template = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>items</key>
    <array>
      <dict>
        <key>assets</key>
        <array>
          <dict>
            <key>kind</key>
            <string>software-package</string>
            <key>url</key>
            <string><![CDATA[{url}]]></string>
          </dict>
          <dict>
            <key>kind</key>
            <string>full-size-image</string>
            <key>url</key>
            <string><![CDATA[{redirect_url}]]></string>
          </dict>
          <dict>
            <key>kind</key>
            <string>display-image</string>
            <key>url</key>
            <string><![CDATA[{redirect_url}]]></string>
          </dict>
        </array>
        <key>metadata</key>
        <dict>
          <key>bundle-identifier</key>
          <string><![CDATA[{package_name}]]></string>
          <key>bundle-version</key>
          <string>1.0.0</string>
          <key>kind</key>
          <string>software</string>
          <key>title</key>
          <string>{appname}</string>
        </dict>
      </dict>
    </array>
  </dict>
</plist>"""


accounts = [
]

reseller_accounts = {
}


excluded_accounts = (

)
