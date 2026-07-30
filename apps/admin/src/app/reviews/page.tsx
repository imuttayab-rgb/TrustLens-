import { Card, CardContent, CardHeader, CardTitle } from '@trustlens/ui';

export const metadata = { title: 'Review queue' };

export default function ReviewQueuePage() {
  return (
    <main className="p-8">
      <h1 className="text-2xl font-bold">Review queue</h1>
      <p className="text-muted-foreground mt-1">
        Cases ordered by priority, then age. Most are opened by the system - a borderline face
        match or a device cluster - not by a seller.
      </p>

      <Card className="mt-8">
        <CardHeader>
          <CardTitle>What a reviewer sees</CardTitle>
        </CardHeader>
        <CardContent className="text-muted-foreground space-y-2 text-sm">
          <p>
            Each case shows the CNIC image and selfie side by side, the OCR fields, the face
            similarity <em>and the threshold that was in force at the time</em>, the device cluster
            and the listing findings.
          </p>
          <p>
            A reviewer approves or rejects the evidence, which triggers a recomputation. Reviewers
            deliberately cannot override a score - only an admin can bypass the engine, and only
            with a written reason.
          </p>
        </CardContent>
      </Card>
    </main>
  );
}
