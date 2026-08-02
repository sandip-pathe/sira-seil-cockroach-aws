import Image from "next/image";

export function CombinedBrandLogo({
  className,
  priority = false,
}: {
  className?: string;
  priority?: boolean;
}) {
  return (
    <Image
      alt="SIRA and SEIL"
      className={className}
      height={661}
      priority={priority}
      src="/brand/sira-seil-lockup.png"
      width={900}
    />
  );
}
