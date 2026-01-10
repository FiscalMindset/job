#!/usr/bin/env python3
"""Test profile analysis with GitHub token and LinkedIn Playwright scraping."""

from enrichment.profile_report import ProfileReportGenerator
import config

print("="*70)
print("🧪 TESTING PROFILE ANALYSIS")
print("="*70)
print(f"🔑 GitHub Token: {'✅ Configured' if config.GITHUB_TOKEN else '❌ Missing'}")
print(f"👤 GitHub: {config.YOUR_GITHUB}")
print(f"💼 LinkedIn: {config.YOUR_LINKEDIN}")
print("="*70)
print()

generator = ProfileReportGenerator()
report = generator.generate_report()
result_file = generator.save_report(report)

print()
print("="*70)
print("✅ FINAL RESULTS")
print("="*70)
print(f"📊 GitHub Repos Analyzed: {len(report['github_analysis']['all_repos'])}")
print(f"💬 LinkedIn Posts Analyzed: {len(report['linkedin_analysis']['posts'])}")
print(f"🎯 Hiring Opportunities Found: {len(report['linkedin_analysis']['hiring_opportunities'])}")
print(f"📁 Portfolio Projects: {len(report['projects'])}")
print(f"📄 Report saved to: {result_file}")
print("="*70)
