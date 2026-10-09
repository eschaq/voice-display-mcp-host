/**
 * What was heard and what was said, under the card.
 *
 * Captions are not decoration on a voice display: they are how somebody
 * across the room, or with the sound off, follows what is happening.
 */
export function CaptionBar({
  heard,
  said,
}: {
  heard: string | null;
  said: string | null;
}): React.JSX.Element {
  return (
    <div className="captionbar">
      <span className="speaker">You</span>
      <span className="said heard" data-testid="heard">
        {heard ?? ""}
      </span>
      <span className="speaker">Display</span>
      <span className="said" data-testid="caption">
        {said ?? ""}
      </span>
    </div>
  );
}
