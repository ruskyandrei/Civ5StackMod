// WORK-ONLY shared API stage. No refresh, pointer exposure or gameplay writes.
// Signature for CvDangerPlots.h:
// bool AppendStackDangerCacheDescriptor(const CvPlot& plot, int* words,
//     unsigned capacity, unsigned& used) const;
bool CvDangerPlots::AppendStackDangerCacheDescriptor(const CvPlot& plot,
 int* words, unsigned capacity, unsigned& used) const
{
 const int index=plot.GetPlotIndex();
 if(m_bDirty||!words||used>capacity||index<0||(size_t)index>=m_DangerPlots.size()||!m_DangerPlots[index].m_pPlot)return false;
 const CvDangerPlotContents& contents=m_DangerPlots[index];
 const unsigned remaining=capacity-used;
 // Format1: version, improvement, fog, flat, units count, cities count;
 // each source contributes its ordered owner/ID pair. Validate ALL size
 // arithmetic before writing; failure leaves the caller's used count intact.
 if(remaining<6)return false;
 const unsigned pairs=(remaining-6)/2;
 if(contents.m_apUnits.size()>pairs||contents.m_apCities.size()>pairs-contents.m_apUnits.size())return false;
 words[used++]=1;
 words[used++]=contents.m_iImprovementDamage;
 words[used++]=contents.m_iFogCount;
 words[used++]=contents.m_bFlatPlotDamage?1:0;
 words[used++]=(int)contents.m_apUnits.size();
 for(size_t i=0;i<contents.m_apUnits.size();++i){words[used++]=contents.m_apUnits[i].first;words[used++]=contents.m_apUnits[i].second;}
 words[used++]=(int)contents.m_apCities.size();
 for(size_t i=0;i<contents.m_apCities.size();++i){words[used++]=contents.m_apCities[i].first;words[used++]=contents.m_apCities[i].second;}
 return true;
}
