***REMOVED*** Home Assistant Brands Submission Guide

Submit your Cable Modem Monitor icons to the Home Assistant Brands repository for official branding support.

***REMOVED******REMOVED*** Why Submit to Brands?

✅ **Official Icons** - Icons appear throughout Home Assistant UI
✅ **Professional Look** - Better user experience
✅ **HACS Requirement** - Recommended (though not required) for HACS
✅ **Integration Identity** - Consistent branding across installations

***REMOVED******REMOVED*** Prerequisites

- GitHub account
- Icons prepared (already done! ✅)
- Basic Git knowledge

***REMOVED******REMOVED*** Icon Files Ready

All required files are in `brands_submission/cable_modem_monitor/`:

```
brands_submission/cable_modem_monitor/
├── icon.png      ***REMOVED*** 256x256 - Required ✅
├── icon@2x.png   ***REMOVED*** 512x512 - Required ✅
└── logo.png      ***REMOVED*** 512x512 - Optional but recommended ✅
```

**Verification:**
- ✅ icon.png: 256x256 PNG
- ✅ icon@2x.png: 512x512 PNG
- ✅ logo.png: 512x512 PNG
- ✅ All RGBA with transparency
- ✅ Proper naming convention

***REMOVED******REMOVED*** Step-by-Step Submission

***REMOVED******REMOVED******REMOVED*** 1. Fork the Brands Repository

```bash
***REMOVED*** Visit GitHub and fork the repository
***REMOVED*** https://github.com/home-assistant/brands

***REMOVED*** Or use GitHub CLI
gh repo fork home-assistant/brands --clone
cd brands
```

***REMOVED******REMOVED******REMOVED*** 2. Create Integration Directory

```bash
***REMOVED*** Create directory for custom integration
mkdir -p custom_integrations/cable_modem_monitor

***REMOVED*** Copy your icon files
cp ../cable_modem_monitor/brands_submission/cable_modem_monitor/*.png \
   custom_integrations/cable_modem_monitor/
```

**Directory Structure:**
```
brands/
└── custom_integrations/
    └── cable_modem_monitor/
        ├── icon.png      ***REMOVED*** 256x256
        ├── icon@2x.png   ***REMOVED*** 512x512
        └── logo.png      ***REMOVED*** 512x512 (optional)
```

***REMOVED******REMOVED******REMOVED*** 3. Verify Icon Requirements

Home Assistant Brands has strict requirements:

✅ **File Names:**
- `icon.png` - Standard resolution
- `icon@2x.png` - High resolution (retina)
- `logo.png` - Optional, for branding

✅ **Dimensions:**
- icon.png: Must be 256x256 pixels
- icon@2x.png: Must be 512x512 pixels
- logo.png: 512x512 pixels (if included)

✅ **Format:**
- PNG format only
- RGBA color space (transparency supported)
- Optimized file size (< 50KB recommended)

✅ **Design Guidelines:**
- Simple, recognizable design
- Works well at small sizes
- Transparent background recommended
- Consistent with other Home Assistant icons

***REMOVED******REMOVED******REMOVED*** 4. Create a Branch

```bash
cd brands
git checkout -b add-cable-modem-monitor
```

***REMOVED******REMOVED******REMOVED*** 5. Add and Commit Files

```bash
git add custom_integrations/cable_modem_monitor/
git commit -m "Add Cable Modem Monitor custom integration icons"
```

***REMOVED******REMOVED******REMOVED*** 6. Push to Your Fork

```bash
git push origin add-cable-modem-monitor
```

***REMOVED******REMOVED******REMOVED*** 7. Create Pull Request

1. Go to your forked repository on GitHub
2. Click "Compare & pull request"
3. **Title:** `Add Cable Modem Monitor custom integration`
4. **Description:**

```markdown
***REMOVED******REMOVED*** Summary
Adding icons for the Cable Modem Monitor custom integration.

***REMOVED******REMOVED*** Integration Details
- **Domain:** `cable_modem_monitor`
- **Name:** Cable Modem Monitor
- **Type:** Custom Integration
- **Repository:** https://github.com/kwschulz/cable_modem_monitor
- **Description:** Monitors cable modem signal quality, power levels, and error rates

***REMOVED******REMOVED*** Files Included
- ✅ icon.png (256x256)
- ✅ icon@2x.png (512x512)
- ✅ logo.png (512x512)

***REMOVED******REMOVED*** Verification
- All files are correctly sized
- PNG format with RGBA
- Transparent backgrounds
- Optimized file sizes
- Consistent design across resolutions

***REMOVED******REMOVED*** Additional Info
This integration provides per-channel monitoring for DOCSIS 3.0 cable modems,
helping users track internet connection health and identify signal issues.
```

5. Click "Create pull request"

***REMOVED******REMOVED******REMOVED*** 8. Wait for Review

**Timeline:** 1-2 weeks typically

**Review Process:**
- Automated checks verify icon dimensions
- Maintainers review for quality and compliance
- May request changes to icons
- Once approved, will be merged

**During Review:**
- Respond to any feedback promptly
- Make requested changes if needed
- Keep an eye on PR comments

***REMOVED******REMOVED*** After Approval

Once your PR is merged:

1. **Icons are Live** - Available in next Home Assistant Brands release
2. **Update HACS Submission** - Mention approved brands in HACS PR
3. **Users See Icons** - Automatically displayed in Home Assistant UI
4. **Documentation** - Update README noting official branding

***REMOVED******REMOVED*** Alternative: Quick Submit via GitHub UI

Don't want to use command line? Use GitHub's web interface:

1. **Fork** https://github.com/home-assistant/brands
2. **Navigate** to `custom_integrations/` in your fork
3. **Click** "Add file" → "Create new file"
4. **Name** the file: `cable_modem_monitor/icon.png`
5. **Upload** icon.png
6. **Repeat** for icon@2x.png and logo.png
7. **Commit** with message: "Add Cable Modem Monitor icons"
8. **Create PR** from your fork to upstream

***REMOVED******REMOVED*** Validation Before Submitting

Run these checks locally:

```bash
***REMOVED*** Check dimensions
file brands_submission/cable_modem_monitor/*.png

***REMOVED*** Expected output:
***REMOVED*** icon.png:    PNG image data, 256 x 256, 8-bit/color RGBA
***REMOVED*** icon@2x.png: PNG image data, 512 x 512, 8-bit/color RGBA
***REMOVED*** logo.png:    PNG image data, 512 x 512, 8-bit/color RGBA

***REMOVED*** Check file sizes (should be reasonable, < 50KB each)
ls -lh brands_submission/cable_modem_monitor/
```

***REMOVED******REMOVED*** Common Issues & Solutions

***REMOVED******REMOVED******REMOVED*** Issue: "Icons too large"
**Solution:** Optimize PNGs with tools like:
```bash
***REMOVED*** Using optipng
optipng -o7 icon.png

***REMOVED*** Using pngquant
pngquant --quality=80-95 icon.png
```

***REMOVED******REMOVED******REMOVED*** Issue: "Wrong dimensions"
**Solution:** Resize with ImageMagick:
```bash
convert icon.png -resize 256x256 icon-resized.png
convert icon@2x.png -resize 512x512 icon2x-resized.png
```

***REMOVED******REMOVED******REMOVED*** Issue: "Not RGBA format"
**Solution:** Convert with ImageMagick:
```bash
convert icon.png -type TrueColorAlpha icon-rgba.png
```

***REMOVED******REMOVED*** Resources

- [Home Assistant Brands Repo](https://github.com/home-assistant/brands)
- [Brands Documentation](https://brands.home-assistant.io/)
- [Icon Guidelines](https://github.com/home-assistant/brands/blob/master/CONTRIBUTING.md)
- [Custom Integration Path](https://github.com/home-assistant/brands/tree/master/custom_integrations)

***REMOVED******REMOVED*** FAQ

**Q: Is this required for HACS?**
A: No, but highly recommended. Improves user experience significantly.

**Q: How long does approval take?**
A: Usually 1-2 weeks, sometimes faster.

**Q: Can I update icons later?**
A: Yes! Submit a new PR with updated icons.

**Q: What if my PR is rejected?**
A: Address feedback and resubmit. Maintainers are helpful!

**Q: Do I need permission?**
A: No permission needed for custom integrations in `custom_integrations/` folder.

***REMOVED******REMOVED*** Next Steps After Brands Submission

1. ✅ Submit to Brands (this guide)
2. ⏳ Wait for brands approval (1-2 weeks)
3. 🚀 Submit to HACS Default (can do in parallel!)
4. 📢 Announce to community

---

**Ready to Submit!** All your icons are prepared and validated. Just follow the steps above! 🎨

**Estimated Time:** 15-30 minutes for submission
**Review Time:** 1-2 weeks
**Difficulty:** Easy ⭐⭐☆☆☆
