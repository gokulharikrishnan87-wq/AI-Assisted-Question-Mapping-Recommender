# Quick Start Guide

**Get up and running in 5 minutes!**

## 🚀 For Business Users

### Option 1: Use the Interactive UI (Recommended)

```bash
# 1. Navigate to project directory
cd AI-Assisted-Question-Mapping-Recommender

# 2. Start the enhanced UI
./start_ui_enhanced.sh

# 3. Open browser
# Go to: http://localhost:8501

# 4. Click "Start Mapping All Questions"
# Wait ~2 minutes for processing

# 5. Export results
# Click "Export to CSV" button
```

**What you get:**
- Interactive visualization of all 829 mappings
- Filter by section or confidence
- View top 5 alternatives per question
- Export to CSV with full metadata

---

### Option 2: Generate CSV Directly

```bash
# Run the batch processor
python map_all_questions_enhanced.py

# Find output file
# Look for: rsc_slcp_mappings_enhanced_YYYYMMDD_HHMMSS.csv
```

**What you get:**
- Complete CSV with 829 rows
- 29 columns including SLCP Key, Number, Section
- Top 5 alternatives with metadata
- Ready for Excel/Google Sheets

---

## 🔧 For Developers

### First Time Setup

```bash
# 1. Install dependencies
pip install -e ".[local-embeddings]"

# 2. Verify installation
python -c "from mapper_copilot.providers.embeddings import SentenceTransformerEmbedder; print('✅ Ready')"

# 3. Run tests
pytest tests/test_embeddings.py -v
```

### Key Files to Review

1. **`PROJECT_SUMMARY.md`** ← Start here!
2. **`src/mapper_copilot/providers/embeddings.py`** ← Core implementation
3. **`ui_enhanced.py`** ← Enhanced UI
4. **`tests/test_embeddings.py`** ← Test examples

### Quick Test

```bash
# Test with real data
python test_real_data.py

# Expected output:
# ✅ 829 RSC questions loaded
# ✅ 2,554 SLCP questions indexed
# ✅ Semantic matching operational
```

---

## 📊 Understanding the Output

### CSV Column Structure

**Basic Info:**
- `RSC_Key`, `RSC_Section`, `RSC_Question`

**Best Match:**
- `Best_SLCP_Key` - Use this to look up in SLCP system ⭐
- `Best_SLCP_Number` - Reference number ⭐
- `Best_SLCP_Section` - Which domain it belongs to ⭐
- `Best_SLCP_Question` - Full text
- `Confidence` - How good the match is (0-100%)

**Alternatives:**
- `Alt_1` through `Alt_5` - Each with Key, Number, Section, Question

### How to Use the Results

1. **Sort by confidence** - Start with highest quality matches
2. **Filter by RSC section** - Review related questions together
3. **Check alternatives** - If best match isn't right, review top 5
4. **Validate with SMEs** - Business experts review and approve

---

## ⚙️ Configuration

### Quick Config

Create `.env` file:

```bash
# Use local embeddings (no AWS needed)
PROVIDER=local
EMBEDDING_MODEL_ID=all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384
```

### Model Options

**Fast (Recommended for testing):**
```bash
EMBEDDING_MODEL_ID=all-MiniLM-L6-v2  # 384-dim, 120MB
```

**Better Quality (For production):**
```bash
EMBEDDING_MODEL_ID=all-mpnet-base-v2  # 768-dim, 420MB
EMBEDDING_DIMENSION=768
```

---

## 🎯 What's Next?

### Immediate Actions

1. ✅ **Review** the generated mappings CSV
2. ✅ **Validate** with subject matter experts
3. ✅ **Document** any corrections/feedback
4. ✅ **Use** approved mappings in production

### Future Enhancements

- Fine-tune on validated mappings
- Integrate actual LLM for better confidence scores
- Add multi-language support
- Build feedback loop for continuous improvement

---

## 🆘 Troubleshooting

### Problem: Model download is slow

**Solution:** First time only - model downloads from HuggingFace (~120MB). Subsequent runs use cached model.

### Problem: UI won't start

**Check:**
```bash
# Are data files present?
ls -lh "RSC Questions.xlsx" slcp_data_dictionary.json

# Is streamlit installed?
pip list | grep streamlit

# Check logs
tail -f /tmp/streamlit_enhanced.log
```

### Problem: Import errors

**Solution:**
```bash
# Reinstall with dependencies
pip install -e ".[local-embeddings]"
```

---

## 📞 Need Help?

1. **Check** `PROJECT_SUMMARY.md` for detailed documentation
2. **Review** `TESTING_GUIDE.md` for testing help
3. **Look at** test files for code examples
4. **Check logs** in `/tmp/` directory

---

## 🎉 Success Checklist

- [ ] Dependencies installed
- [ ] Data files in place (RSC Questions.xlsx, slcp_data_dictionary.json)
- [ ] UI starts successfully
- [ ] Can generate mappings
- [ ] CSV export works
- [ ] Results look reasonable

**All checked?** You're ready to go! 🚀
