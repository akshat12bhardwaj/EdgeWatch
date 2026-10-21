# Limitations (living document)

These limitations are known before any experiment. Add the ones discovered during the work.

## Research and literature
- Round-1 review: 8 sources were read in full; others at abstract or metadata level. IEEE Xplore and ACM DL were not searched directly in round 1 ([SEARCH_PROTOCOL.md](../research/SEARCH_PROTOCOL.md)).
- The novelty claim covers the reviewed literature only, as of the search date.

## Data
- All public datasets are simulated or testbed captures. Our lab is also a lab.
- MQTTset likely has one episode per attack class, which limits episode-held-out evaluation.
- Cross-dataset overlap is limited to the benign, flood, malformed, and brute-force families.
- Our features differ from the published ones, so our numbers are not directly comparable with prior papers (E1-a gives an anchor).

## System
- Plaintext MQTT only, unless E8 is run. Under TLS a passive observer loses all `mqtt.*` features.
- Per-source-IP windows: NAT or shared IPs merge sources; DDoS from many low-rate sources is harder to detect.
- One gateway device model. Results may not transfer to other hardware.
- Detection only. No prevention or mitigation is evaluated.
- Passive detection cannot see payload-level abuse by authorised clients, or authorisation misuse with valid credentials.

## Evaluation
- Lab attacks are reproductions of the dataset attack classes, not real adversaries.
- Benign-lab traffic is "different from training", not "real-world production".
- Model scores are not probabilities unless calibration passes.
