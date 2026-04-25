<?php

declare(strict_types=1);

namespace IAIso\Consent;

/** Builder for {@see Verifier}. */
final class VerifierBuilder
{
    private ?string $hsKey = null;
    private mixed $rsKey = null;
    private Algorithm $algorithm = Algorithm::HS256;
    private string $issuer = 'iaiso';
    private ?RevocationList $revocationList = null;
    private int $leewaySeconds = 5;
    /** @var (callable():int)|null */
    private $clock = null;

    public function hsKey(string $bytes): self                 { $this->hsKey = $bytes; return $this; }
    public function rsKey(mixed $key): self                    { $this->rsKey = $key; return $this; }
    public function algorithm(Algorithm $a): self              { $this->algorithm = $a; return $this; }
    public function issuer(string $iss): self                  { $this->issuer = $iss; return $this; }
    public function revocationList(?RevocationList $rl): self  { $this->revocationList = $rl; return $this; }
    public function leewaySeconds(int $s): self                { $this->leewaySeconds = $s; return $this; }

    /** @param callable():int $clock */
    public function clock(callable $clock): self               { $this->clock = $clock; return $this; }

    public function build(): Verifier
    {
        $clk = $this->clock ?? fn(): int => time();
        return new Verifier($this->hsKey, $this->rsKey, $this->algorithm,
            $this->issuer, $this->revocationList, $this->leewaySeconds, $clk);
    }
}
