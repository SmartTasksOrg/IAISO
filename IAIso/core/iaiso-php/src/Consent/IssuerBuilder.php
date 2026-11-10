<?php

declare(strict_types=1);

namespace IAIso\Consent;

/** Builder for {@see Issuer}. */
final class IssuerBuilder
{
    private ?string $hsKey = null;
    private mixed $rsKey = null;
    private Algorithm $algorithm = Algorithm::HS256;
    private string $issuer = 'iaiso';
    private int $defaultTtlSeconds = 3600;
    /** @var (callable():int)|null */
    private $clock = null;

    public function hsKey(string $bytes): self      { $this->hsKey = $bytes; return $this; }
    public function rsKey(mixed $key): self         { $this->rsKey = $key; return $this; }
    public function algorithm(Algorithm $a): self   { $this->algorithm = $a; return $this; }
    public function issuer(string $iss): self       { $this->issuer = $iss; return $this; }
    public function defaultTtlSeconds(int $s): self { $this->defaultTtlSeconds = $s; return $this; }

    /** @param callable():int $clock */
    public function clock(callable $clock): self    { $this->clock = $clock; return $this; }

    public function build(): Issuer
    {
        $clk = $this->clock ?? fn(): int => time();
        return new Issuer($this->hsKey, $this->rsKey, $this->algorithm,
            $this->issuer, $this->defaultTtlSeconds, $clk);
    }
}
