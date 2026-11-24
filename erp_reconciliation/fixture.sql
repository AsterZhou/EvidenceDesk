-- Entirely invented procurement snapshot. Prices are integer cents.
CREATE TABLE po_lines (
    po_line TEXT PRIMARY KEY, supplier TEXT NOT NULL, currency TEXT NOT NULL,
    ordered_qty INTEGER NOT NULL CHECK(ordered_qty>0), unit_price_cents INTEGER NOT NULL CHECK(unit_price_cents>=0)
);
CREATE TABLE receipts (
    receipt_id TEXT PRIMARY KEY, po_line TEXT NOT NULL REFERENCES po_lines(po_line),
    quantity INTEGER NOT NULL CHECK(quantity>0)
);
CREATE TABLE invoices (
    import_id TEXT PRIMARY KEY, supplier TEXT NOT NULL, invoice_number TEXT NOT NULL, currency TEXT NOT NULL
);
CREATE TABLE invoice_lines (
    row_id TEXT PRIMARY KEY, import_id TEXT NOT NULL REFERENCES invoices(import_id),
    po_line TEXT NOT NULL, quantity INTEGER NOT NULL CHECK(quantity>0),
    unit_price_cents INTEGER NOT NULL CHECK(unit_price_cents>=0)
);
INSERT INTO po_lines VALUES
('P10-1','ORCHID','CNY',10,1250),('P11-1','ORCHID','CNY',5,800),
('P12-1','CEDAR','CNY',3,700),('P13-1','CEDAR','USD',4,1500),
('P14-1','ORCHID','CNY',1,1000),('P15-1','CEDAR','CNY',6,200);
INSERT INTO receipts VALUES
('R1','P10-1',3),('R2','P10-1',5),('R3','P11-1',5),('R4','P12-1',3),
('R5','P13-1',4),('R6','P14-1',1);
INSERT INTO invoices VALUES
('I1','ORCHID','A101','CNY'),('I2','ORCHID','A102','CNY'),('I3','ORCHID','A103','CNY'),
('I4','CEDAR','B204','CNY'),('I5','CEDAR','B204','CNY'),('I6','CEDAR','B205','CNY'),
('I7','ORCHID','A107','CNY'),('I8','MAPLE','M108','CNY'),('I9','CEDAR','B209','CNY'),
('I10','ORCHID','A110','CNY');
INSERT INTO invoice_lines VALUES
('L01','I1','P10-1',3,1250),('L02','I2','P10-1',5,1250),
('L03','I3','P11-1',5,820),('L04','I4','P12-1',1,700),('L05','I5','P12-1',1,700),
('L06','I6','P13-1',4,1500),('L07','I7','P99-1',1,500),('L08','I8','P14-1',1,1000),
('L09','I9','P15-1',2,200),('L10','I10','P11-1',2,800);
