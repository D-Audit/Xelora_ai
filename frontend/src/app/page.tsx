import { MarketingNav } from '@/components/marketing/nav';
import { MarketingFooter } from '@/components/marketing/footer';
import {
  ClosingCta, Examples, Faq, Hero, HowItWorks, PricingPreview, Product, Security,
} from '@/components/marketing/landing';

export default function HomePage() {
  return (
    <>
      <MarketingNav />
      <main>
        <Hero />
        <Product />
        <Examples />
        <HowItWorks />
        <Security />
        <PricingPreview />
        <Faq />
        <ClosingCta />
      </main>
      <MarketingFooter />
    </>
  );
}
