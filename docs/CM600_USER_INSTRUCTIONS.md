***REMOVED*** Instructions for Netgear CM600 Users

Hey there! Thanks for your patience. We've made it super easy to help us add support for your Netgear CM600 modem.

***REMOVED******REMOVED*** The Easy Way (Just 4 Steps!)

***REMOVED******REMOVED******REMOVED*** Step 1: Install the Integration

Even though your CM600 isn't fully supported yet, you can still install the integration:

1. Go to Home Assistant
2. Click **Settings** → **Devices & Services**
3. Click **+ Add Integration**
4. Search for "Cable Modem Monitor"
5. Enter your modem's IP address: `192.168.100.1`
6. For username/password: **just press Enter** (leave blank)
7. Click **Submit**

✅ The integration will install! (It might say "Unknown Modem" - that's OK!)

***REMOVED******REMOVED******REMOVED*** Step 2: Press One Button

After installation:

1. Go to **Settings** → **Devices & Services** → **Cable Modem Monitor**
2. Find the button called **"Capture HTML"**
3. **Press it!**
4. Wait about 10-15 seconds

The capture tool will:
- Fetch the main modem pages
- **Automatically follow links** to discover all modem pages
- Capture up to 20+ pages automatically!

You'll see a notification that says "HTML Capture Complete"

***REMOVED******REMOVED******REMOVED*** Step 3: Download the File

Within 5 minutes of pressing the button:

1. Go to **Settings** → **Devices**
2. Find **"Cable Modem"** in the list
3. Click on it
4. Click the **three dots menu** (⋮) in the top right
5. Select **"Download diagnostics"**
6. Save the file (it will be a .json file)

***REMOVED******REMOVED******REMOVED*** Step 4: Share the File

1. Come back to this GitHub issue
2. Drag and drop the .json file into a comment
3. Add a note like "Here's my CM600 HTML capture!"
4. Click **Comment**

**That's it!** 🎉

---

***REMOVED******REMOVED*** What Happens Next?

1. I'll use your file to create support for the CM600 (takes about 2-6 hours)
2. I'll test it with your HTML
3. I'll release it in the next version
4. You update the integration
5. Your modem works perfectly! 🚀

---

***REMOVED******REMOVED*** Privacy Note

The file automatically removes:
- ❌ Your MAC address
- ❌ Serial numbers
- ❌ Private IP addresses
- ❌ Passwords

It keeps:
- ✅ Channel data (what we need to build the parser)
- ✅ Signal levels
- ✅ Modem model info

---

***REMOVED******REMOVED*** Troubleshooting

***REMOVED******REMOVED******REMOVED*** "I can't install the integration"
Try entering the modem's IP as just `192.168.100.1` without http:// or anything else.

***REMOVED******REMOVED******REMOVED*** "I don't see the Capture HTML button"
Make sure you completed Step 1 and the integration installed. Check Settings → Devices & Services.

***REMOVED******REMOVED******REMOVED*** "The download link expired"
No problem! Just press the "Capture HTML" button again, then download diagnostics within 5 minutes.

***REMOVED******REMOVED******REMOVED*** "My modem requires a password"
Try installing again, and when it asks for username/password, enter your modem's admin credentials (usually on a label on the modem).

---

***REMOVED******REMOVED*** Still Stuck?

Reply to this issue with:
- What step you're stuck on
- Any error messages you see
- I'll help you out!

Thanks for helping make this integration better for everyone! 🙌
