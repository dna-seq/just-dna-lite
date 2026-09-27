# rhd_deletion (test fixture)

The RHD half of `antonkulaga/blood_groups@0.1.0`, cut out verbatim (haplotypes, diplotypes and the
rs1132760 resolution row) so the phenotype caller's deletion-allele reading can be tested on the
shape a published module really has: `RHD` carries `T` at rs1132760 and `RHD_deletion` carries
`<DEL:68163>` there, both with `requires_callable=true`.

That span runs from rs1132760 for 68,163 bases, i.e. 1:25,284,732-25,352,894. It starts about 12 kb
inside RHD (1:25,272,393-25,330,445) and ends about 22 kb past it, so it is an approximation of the
common RhD-negative deletion, not its coordinates. The caller reads the span as authored; on one real
genome that leaves a 51.6 kb call-free stretch inside it, which the caller reports as unsettled rather
than guessing.

RHD lies wholly inside GIAB's segmental-duplication mask (it is near-identical to RHCE), so rs1132760
is never restored to reference. What a callset can still show is coverage inside the span.
